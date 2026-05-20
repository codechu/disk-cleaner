"""TreemapController — disk map state machine.

Owned state:

- ``root_node`` / ``current_node`` / ``history`` (drill stack)
- ``path`` (the path in the entry)
- ``viz_mode`` ("treemap" | "sunburst")
- ``_busy`` + ``_cancel_event``

View responsibilities (hover, fade animation, PNG export, cairo
drawing) are **not part of this class**. The View handles click/up
events, calls ``hit_test`` to find the node, and calls
:meth:`drill_in` / :meth:`drill_up`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from .._bus import bus
from ..config import HOME
from ..i18n import _
from ..settings import SETTINGS, save_settings
from ..storage.du_cache import lookup_cached_dir_size, store_dir_size
from ..utils import ThrottledProgress, human
from ..viz import TreeNode, build_tree, hit_test, sunburst_hit_test

# Reuse du-cache entries for at most 6h before a fresh re-walk.
_DU_CACHE_TTL_SEC = 6 * 3600


def _disk_cache_provider(p: Path) -> int | None:
    """:class:`SizeProvider` — return cached dir size if fresh, else None."""
    return lookup_cached_dir_size(p, ttl=_DU_CACHE_TTL_SEC)


def _persist_dir_sizes(node: TreeNode) -> None:
    """DFS-walk a built tree and write every directory's size back to du_cache.

    Lets the next scan short-circuit via the size_provider.
    """
    if not node.is_dir or node.is_other:
        return
    store_dir_size(node.path, node.size)
    for c in node.children:
        _persist_dir_sizes(c)


class TreemapController:
    """Disk map state machine — view-independent."""

    def __init__(self) -> None:
        # State
        self.root_node: TreeNode | None = None
        self.current_node: TreeNode | None = None
        self.history: list[TreeNode] = []
        self._cancel_event = threading.Event()
        self._busy = False
        self.viz_mode: str = SETTINGS.get("viz_mode", "treemap")
        saved_entries = SETTINGS.get("entries", {})
        self.path: str = saved_entries.get("treemap", str(HOME))

        # Observer callbacks (registered by the View; may be invoked from worker threads)
        self.on_busy_changed: Callable[[bool], None] = _noop
        self.on_root_loaded: Callable[[TreeNode], None] = _noop
        self.on_current_changed: Callable[[TreeNode, list[TreeNode]], None] = _noop2
        self.on_viz_mode_changed: Callable[[str], None] = _noop
        self.on_progress: Callable[[str], None] = _noop
        self.on_log: Callable[[str], None] = _noop
        self.on_error: Callable[[str], None] = _noop

    # ---- Commands ----

    def set_path(self, path: str) -> None:
        """Called when the user changes the path entry."""
        if path == self.path:
            return
        self.path = path
        entries = SETTINGS.get("entries", {})
        entries["treemap"] = path
        SETTINGS["entries"] = entries
        save_settings(SETTINGS)

    def set_viz_mode(self, mode: str) -> None:
        """Switch between treemap / sunburst — persisted to settings."""
        if mode == self.viz_mode:
            return
        self.viz_mode = mode
        SETTINGS["viz_mode"] = mode
        save_settings(SETTINGS)
        self.on_viz_mode_changed(mode)

    def start_scan(self) -> None:
        """Start a new scan — on a daemon thread."""
        if self._busy:
            return
        self._cancel_event.clear()
        self._set_busy(True)
        path = self.path
        self.on_log("\n--- " + _("Disk map: scanning {path}").format(path=path) + " ---\n")
        bus.emit("treemap.scan.started", path=path)
        threading.Thread(target=self._scan_thread, args=(path,), daemon=True).start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def drill_in(self, target: TreeNode) -> None:
        """Drill into a directory (is_dir only)."""
        if not self.current_node or target is self.current_node:
            return
        if not target.is_dir:
            return
        prev = self.current_node
        self.history.append(self.current_node)
        self.current_node = target
        self.path = target.path
        self.on_current_changed(self.current_node, self.history)
        bus.emit(
            "treemap.drill",
            direction="in",
            from_path=prev.path,
            to_path=target.path,
        )

    def drill_up(self) -> None:
        """Go up one level (pop from history).

        If the node we land on has never had its children loaded
        (``children`` is empty but ``is_dir`` is True) a fresh scan is
        kicked off automatically — otherwise the cached subtree is kept.
        """
        if not self.history or not self.current_node:
            return
        prev_path = self.current_node.path
        self.current_node = self.history.pop()
        self.path = self.current_node.path
        self.on_current_changed(self.current_node, self.history)
        bus.emit(
            "treemap.drill",
            direction="up",
            from_path=prev_path,
            to_path=self.current_node.path,
        )
        if self.current_node.is_dir and not self.current_node.children and not self._busy:
            self.start_scan()

    def drill_to(self, target: TreeNode) -> None:
        """Breadcrumb click — pop history down to ``target``."""
        if not self.current_node:
            return
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i] is target:
                prev_path = self.current_node.path
                self.current_node = self.history[i]
                self.history = self.history[:i]
                self.path = self.current_node.path
                self.on_current_changed(self.current_node, self.history)
                bus.emit(
                    "treemap.drill",
                    direction="to",
                    from_path=prev_path,
                    to_path=self.current_node.path,
                )
                return

    def drill_to_path(self, target_path: str) -> bool:
        """Drill by breadcrumb path string — True if found."""
        if not self.current_node:
            return False
        target_path = target_path.rstrip("/") or "/"
        for h in self.history:
            if h.path.rstrip("/") == target_path:
                self.drill_to(h)
                return True
        return False

    # ---- Queries ----

    def hit_test(self, x: float, y: float) -> TreeNode | None:
        """Hit test according to visual mode. Called by the View on click events."""
        if not self.current_node:
            return None
        if self.viz_mode == "sunburst":
            return sunburst_hit_test(self.current_node, x, y)
        return hit_test(self.current_node, x, y)

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def can_go_up(self) -> bool:
        return bool(self.history)

    @property
    def has_node(self) -> bool:
        return self.current_node is not None

    # ---- Internals ----

    def _scan_thread(self, path: str) -> None:
        progress = ThrottledProgress(self.on_progress)
        try:
            node = build_tree(
                path,
                cancel=self._cancel_event,
                progress=progress,
                size_provider=_disk_cache_provider,
            )
        except Exception as e:
            self.on_error(_("Disk map error: {err}").format(err=e))
            node = None
        if node is not None and not self._cancel_event.is_set():
            try:
                _persist_dir_sizes(node)
            except Exception:
                # Caching is opportunistic — never let it break a scan.
                pass
        self._scan_done(node, path)

    def _scan_done(self, node: TreeNode | None, path: str) -> None:
        self._set_busy(False)
        if node is None:
            self.on_progress(_("Scan cancelled or errored."))
            self.on_log(_("Disk map cancelled/errored.") + "\n")
            bus.emit("treemap.scan.finished", path=path, ok=False)
            return
        self.root_node = node
        self.current_node = node
        self.history = []
        self.on_root_loaded(node)
        self.on_current_changed(node, self.history)
        self.on_log(_("Disk map ready: total {size}").format(size=human(node.size)) + "\n")
        bus.emit(
            "treemap.scan.finished",
            path=node.path,
            size=node.size,
            ok=True,
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.on_busy_changed(busy)


def _noop(*_a, **_kw) -> None:
    pass


def _noop2(*_a, **_kw) -> None:
    pass


__all__ = ["TreemapController"]
