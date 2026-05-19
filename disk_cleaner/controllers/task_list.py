"""TaskListController — state machine for scan/select/clean flow.

State owned by a single task-list panel (system cache, project
artifacts, old files, etc.). The View observes this controller and
buttons call controller methods.

Design:

- The task list lives on the controller as ``list[TaskRow]``; each row
  contains render-ready fields (name, risk, path, size_text, checked).
- Sizing / cleanup / preview always run on a daemon thread; cancellation
  uses ``threading.Event``.
- Auto-select rule is parametrized: risk + min size + ``auto_select`` flag.
- Cleanup confirmation is the View's responsibility — the controller
  builds a :class:`CleanPreview` and offers it to the View via callback;
  the View shows a dialog and returns a bool.
- Preview runs on a separate thread + cancel channel; each new request
  cancels the previous one.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .. import events
from ..core.sizing import apparent_size, dir_size, is_sparse, path_size
from ..i18n import _
from ..utils import ThrottledProgress, human


@dataclass
class TaskRow:
    """Render-ready row representation exposed to the View."""

    tid: int  # internal task id (stable)
    name: str
    risk: str  # "low" / "medium" / "high"
    path: str
    desc: str
    size_bytes: int | None = None  # None: not yet measured
    size_text: str = "—"  # human(size) or "unmeasurable"
    checked: bool = False
    status_marker: str = ""  # "✓ " / "✗ " after cleanup


@dataclass
class PreviewItem:
    name: str
    size: int
    is_dir: bool
    is_sparse: bool = False
    nominal_size: int = 0


@dataclass
class PreviewResult:
    """Rich preview data presented to the View.

    The View converts this into its own markup (Pango / HTML / Qt rich
    text).
    """

    path: str
    state: Literal["scanning", "missing", "file", "directory", "error"]
    file_size: int = 0
    items: list[PreviewItem] = field(default_factory=list)
    total_items: int = 0
    error: str = ""


@dataclass
class CleanPreview:
    """Summary for the confirmation dialog."""

    count: int
    total_bytes: int
    items: list[tuple[int, str]]  # (row_index, task_name) — first 20


class TaskListController:
    """Task-list state machine — view-independent."""

    AUTO_SELECT_DEFAULT_MIN_BYTES = 100 * 1024 * 1024  # 100 MB

    def __init__(
        self,
        provider: Callable[..., Iterable[dict[str, Any]]],
        *,
        name: str = "task",
        auto_select: bool = True,
        auto_select_risk: str = "low",
        auto_select_min_bytes: int = AUTO_SELECT_DEFAULT_MIN_BYTES,
    ) -> None:
        self.provider = provider
        self.name = name
        self.auto_select = auto_select
        self.auto_select_risk = auto_select_risk
        self.auto_select_min_bytes = auto_select_min_bytes

        # State
        self.rows: list[TaskRow] = []
        self.tasks: list[dict[str, Any]] = []  # raw, parallel to rows
        self._cancel_event = threading.Event()
        self._preview_cancel = threading.Event()
        self._busy = False
        self._next_tid = 0

        # Observers (may be invoked from worker threads; View handles marshalling)
        self.on_busy_changed: Callable[[bool, str], None] = _noop2
        self.on_rows_replaced: Callable[[list[TaskRow]], None] = _noop
        self.on_row_updated: Callable[[int, TaskRow], None] = _noop2
        self.on_total_changed: Callable[[int, int], None] = _noop2
        self.on_progress: Callable[[str], None] = _noop
        self.on_log: Callable[[str], None] = _noop
        self.on_preview: Callable[[PreviewResult], None] = _noop
        self.on_disk_label_dirty: Callable[[], None] = _noop

    # ---- Public commands ----

    def start_scan(self) -> None:
        if self._busy:
            return
        self._cancel_event.clear()
        self.rows = []
        self.tasks = []
        self._next_tid = 0
        self._set_busy(True, _("Listing items…"))
        self.on_rows_replaced(self.rows)
        self.on_log("\n--- " + _("Scan started") + " ---\n")
        events.emit("scan.started", panel=self.name)
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def cancel(self) -> None:
        self._cancel_event.set()
        self.on_progress(_("Cancelling…"))

    def toggle(self, idx: int) -> None:
        if 0 <= idx < len(self.rows):
            self.rows[idx].checked = not self.rows[idx].checked
            self.on_row_updated(idx, self.rows[idx])
            self._emit_total()

    def select_all(self) -> None:
        for i, r in enumerate(self.rows):
            if not r.checked:
                r.checked = True
                self.on_row_updated(i, r)
        self._emit_total()

    def select_none(self) -> None:
        for i, r in enumerate(self.rows):
            if r.checked:
                r.checked = False
                self.on_row_updated(i, r)
        self._emit_total()

    def start_clean(
        self,
        confirm: Callable[[CleanPreview], bool],
    ) -> bool:
        """Confirm callback is called synchronously (dialog on the View).

        Returns: True if cleanup actually started.
        """
        selected = [(i, self.tasks[i]) for i, r in enumerate(self.rows) if r.checked]
        if not selected:
            return False
        total = sum((self.rows[i].size_bytes or 0) for i, _ in selected)
        preview = CleanPreview(
            count=len(selected),
            total_bytes=total,
            items=[(i, t["name"]) for i, t in selected[:20]],
        )
        if not confirm(preview):
            return False
        self._cancel_event.clear()
        self._set_busy(True, f"0 / {len(selected)}")
        events.emit("clean.started", panel=self.name, count=len(selected))
        threading.Thread(target=self._clean_thread, args=(selected,), daemon=True).start()
        return True

    def request_preview(self, idx: int) -> None:
        """Called when a row is selected — cancels any old preview thread."""
        if not (0 <= idx < len(self.tasks)):
            return
        task = self.tasks[idx]
        path = task.get("path", "")
        # Cancel old thread, fresh event
        self._preview_cancel.set()
        self._preview_cancel = threading.Event()
        self.on_preview(PreviewResult(path=path, state="scanning"))
        threading.Thread(
            target=self._preview_thread,
            args=(path, self._preview_cancel),
            daemon=True,
        ).start()

    # ---- Properties ----

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def total_bytes(self) -> int:
        return sum(r.size_bytes or 0 for r in self.rows if r.checked)

    @property
    def selected_count(self) -> int:
        return sum(1 for r in self.rows if r.checked)

    # ---- Internals — scan ----

    def _scan_thread(self) -> None:
        progress = ThrottledProgress(self.on_progress)
        try:
            tasks = _call_provider(self.provider, self._cancel_event, progress) or []
        except Exception as e:
            self.on_log(_("List error: {err}").format(err=e) + "\n")
            tasks = []

        if self._cancel_event.is_set():
            self._scan_done(cancelled=True)
            return

        # Build rows
        new_rows: list[TaskRow] = []
        for t in tasks:
            tid = self._next_tid
            self._next_tid += 1
            new_rows.append(
                TaskRow(
                    tid=tid,
                    name=t["name"],
                    risk=t.get("risk", "medium"),
                    path=t.get("path", ""),
                    desc=t.get("desc", ""),
                )
            )
        self.tasks = list(tasks)
        self.rows = new_rows
        self.on_rows_replaced(self.rows)
        self.on_progress(f"0 / {len(self.rows)}" if self.rows else _("no items"))

        if not tasks:
            self._scan_done(cancelled=False)
            return

        # Compute sizes one by one
        for idx, t in enumerate(tasks):
            if self._cancel_event.is_set():
                self._scan_done(cancelled=True)
                return
            try:
                size = t["size_fn"]()
            except Exception as e:
                size = None
                self.on_log(_("{name}: error {err}").format(name=t["name"], err=e) + "\n")
            self._apply_size(idx, size)
            self.on_progress(f"{idx + 1} / {len(tasks)}")
        self._scan_done(cancelled=False)

    def _apply_size(self, idx: int, size: int | None) -> None:
        row = self.rows[idx]
        row.size_bytes = size or 0
        row.size_text = human(size) if size is not None else _("unmeasurable")
        if (
            self.auto_select
            and size is not None
            and row.risk == self.auto_select_risk
            and size > self.auto_select_min_bytes
        ):
            row.checked = True
        self.on_row_updated(idx, row)
        self._emit_total()

    def _scan_done(self, *, cancelled: bool) -> None:
        progress_text = _("Cancelled") if cancelled else ""
        self._set_busy(False, progress_text)
        self.on_disk_label_dirty()
        if cancelled:
            self.on_log(_("Scan cancelled.") + "\n")
        elif self.auto_select:
            self.on_log(_("Scan complete. Low-risk items >100MB auto-selected.") + "\n")
        else:
            self.on_log(_("Scan complete.") + "\n")
        events.emit(
            "scan.finished",
            panel=self.name,
            cancelled=cancelled,
            count=len(self.rows),
        )

    # ---- Internals — clean ----

    def _clean_thread(self, selected: list[tuple[int, dict[str, Any]]]) -> None:
        for n, (idx, task) in enumerate(selected, 1):
            if self._cancel_event.is_set():
                self.on_log(
                    "\n"
                    + _("Cleanup cancelled ({done}/{total} completed).").format(
                        done=n - 1, total=len(selected)
                    )
                    + "\n"
                )
                break
            self.on_progress(f"{n} / {len(selected)}")
            self.on_log(f"\n▶ {task['name']}...\n")
            try:
                rc, out = task["clean_fn"]()
            except Exception as e:
                rc, out = 1, _("exception: {err}").format(err=e)
            status = _("✓ ok") if rc == 0 else _("✗ error")
            self.on_log(f"  {status}\n")
            if out and out.strip():
                snippet = out.strip()
                if len(snippet) > 600:
                    snippet = snippet[:600] + _("...(truncated)")
                self.on_log("  " + snippet.replace("\n", "\n  ") + "\n")
            self._refresh_row(idx)
        self._clean_done()

    def _refresh_row(self, idx: int) -> None:
        if not (0 <= idx < len(self.rows)):
            return
        t = self.tasks[idx]
        try:
            size = t["size_fn"]()
        except Exception:
            size = None
        row = self.rows[idx]
        row.size_bytes = size or 0
        row.size_text = human(size) if size is not None else _("unmeasurable")
        row.checked = False
        self.on_row_updated(idx, row)
        self._emit_total()
        self.on_disk_label_dirty()

    def _clean_done(self) -> None:
        self._set_busy(False, "")
        self.on_log("\n--- " + _("Cleanup complete") + " ---\n")
        events.emit("clean.finished", panel=self.name)

    # ---- Internals — preview ----

    def _preview_thread(self, path: str, cancel: threading.Event) -> None:
        p = Path(os.path.expanduser(path)) if path else None
        if not p or not p.exists():
            self.on_preview(PreviewResult(path=path, state="missing"))
            return
        if p.is_file():
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            self.on_preview(
                PreviewResult(
                    path=str(p),
                    state="file",
                    file_size=size,
                )
            )
            return
        try:
            children = list(p.iterdir())
        except (PermissionError, OSError) as e:
            self.on_preview(
                PreviewResult(
                    path=str(p),
                    state="error",
                    error=str(e),
                )
            )
            return
        children = children[:200]
        items: list[PreviewItem] = []
        for child in children:
            if cancel.is_set():
                return
            try:
                if child.is_symlink():
                    continue
                if child.is_file():
                    size = path_size(child)
                    is_sp = is_sparse(child)
                    items.append(
                        PreviewItem(
                            name=child.name,
                            size=size,
                            is_dir=False,
                            is_sparse=is_sp,
                            nominal_size=apparent_size(child) if is_sp else 0,
                        )
                    )
                elif child.is_dir():
                    size = dir_size(child)
                    items.append(
                        PreviewItem(
                            name=child.name,
                            size=size,
                            is_dir=True,
                        )
                    )
            except OSError:
                continue
        if cancel.is_set():
            return
        items.sort(key=lambda x: -x.size)
        self.on_preview(
            PreviewResult(
                path=str(p),
                state="directory",
                items=items[:8],
                total_items=len(items),
            )
        )

    # ---- Internals — bookkeeping ----

    def _emit_total(self) -> None:
        self.on_total_changed(self.selected_count, self.total_bytes)

    def _set_busy(self, busy: bool, progress_text: str) -> None:
        self._busy = busy
        self.on_busy_changed(busy, progress_text)


def _call_provider(
    provider: Callable[..., Any],
    cancel: threading.Event,
    progress: Callable[[str], None],
) -> Iterable[dict[str, Any]] | None:
    """Provider contract is flexible: use whichever signature it supports."""
    try:
        return provider(cancel, progress=progress)
    except TypeError:
        pass
    try:
        return provider(cancel)
    except TypeError:
        pass
    return provider()


def _noop(*_a, **_kw) -> None:
    pass


def _noop2(*_a, **_kw) -> None:
    pass


__all__ = [
    "CleanPreview",
    "PreviewItem",
    "PreviewResult",
    "TaskListController",
    "TaskRow",
]
