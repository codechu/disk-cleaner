"""TreemapController — disk haritası state machine'i.

Sahip olunan state:

- ``root_node`` / ``current_node`` / ``history`` (drill stack)
- ``path`` (entry'deki yol)
- ``viz_mode`` ("treemap" | "sunburst")
- ``_busy`` + ``_cancel_event``

View'ın görevi (hover, fade animasyon, PNG export, cairo çizim) **bu
sınıfta yok**. View click/up event'ini alır, ``hit_test`` ile node bulur,
:meth:`drill_in` / :meth:`drill_up` çağırır.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from .. import events
from ..config import HOME
from ..i18n import _
from ..settings import SETTINGS, save_settings
from ..utils import ThrottledProgress, human
from ..viz.sunburst import sunburst_hit_test
from ..viz.tree_node import TreeNode, build_tree
from ..viz.treemap import hit_test


class TreemapController:
    """Disk haritası state machine'i — View-bağımsız."""

    def __init__(self) -> None:
        # State
        self.root_node: Optional[TreeNode] = None
        self.current_node: Optional[TreeNode] = None
        self.history: list[TreeNode] = []
        self._cancel_event = threading.Event()
        self._busy = False
        self.viz_mode: str = SETTINGS.get("viz_mode", "treemap")
        saved_entries = SETTINGS.get("entries", {})
        self.path: str = saved_entries.get("treemap", str(HOME))

        # Observer callbacks (View register eder; worker thread'den çağrılabilir)
        self.on_busy_changed: Callable[[bool], None] = _noop
        self.on_root_loaded: Callable[[TreeNode], None] = _noop
        self.on_current_changed: Callable[[TreeNode, list[TreeNode]], None] = _noop2
        self.on_viz_mode_changed: Callable[[str], None] = _noop
        self.on_progress: Callable[[str], None] = _noop
        self.on_log: Callable[[str], None] = _noop
        self.on_error: Callable[[str], None] = _noop

    # ---- Commands ----

    def set_path(self, path: str) -> None:
        """Kullanıcı yol entry'sini değiştirdiğinde."""
        if path == self.path:
            return
        self.path = path
        entries = SETTINGS.get("entries", {})
        entries["treemap"] = path
        SETTINGS["entries"] = entries
        save_settings(SETTINGS)

    def set_viz_mode(self, mode: str) -> None:
        """treemap / sunburst arası geçiş — settings'e kaydedilir."""
        if mode == self.viz_mode:
            return
        self.viz_mode = mode
        SETTINGS["viz_mode"] = mode
        save_settings(SETTINGS)
        self.on_viz_mode_changed(mode)

    def start_scan(self) -> None:
        """Yeni tarama başlat — daemon thread'de."""
        if self._busy:
            return
        self._cancel_event.clear()
        self._set_busy(True)
        path = self.path
        self.on_log(
            "\n--- "
            + _("Disk map: scanning {path}").format(path=path)
            + " ---\n"
        )
        events.emit("treemap.scan.started", path=path)
        threading.Thread(
            target=self._scan_thread, args=(path,), daemon=True
        ).start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def drill_in(self, target: TreeNode) -> None:
        """Bir dizine in (sadece is_dir)."""
        if not self.current_node or target is self.current_node:
            return
        if not target.is_dir:
            return
        prev = self.current_node
        self.history.append(self.current_node)
        self.current_node = target
        self.path = target.path
        self.on_current_changed(self.current_node, self.history)
        events.emit(
            "treemap.drill", direction="in",
            from_path=prev.path, to_path=target.path,
        )

    def drill_up(self) -> None:
        """Bir üst dizine çık (history'den pop)."""
        if not self.history or not self.current_node:
            return
        prev_path = self.current_node.path
        self.current_node = self.history.pop()
        self.path = self.current_node.path
        self.on_current_changed(self.current_node, self.history)
        events.emit(
            "treemap.drill", direction="up",
            from_path=prev_path, to_path=self.current_node.path,
        )

    def drill_to(self, target: TreeNode) -> None:
        """Breadcrumb tıklaması — history'de target'a kadar pop."""
        if not self.current_node:
            return
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i] is target:
                prev_path = self.current_node.path
                self.current_node = self.history[i]
                self.history = self.history[:i]
                self.path = self.current_node.path
                self.on_current_changed(self.current_node, self.history)
                events.emit(
                    "treemap.drill", direction="to",
                    from_path=prev_path, to_path=self.current_node.path,
                )
                return

    def drill_to_path(self, target_path: str) -> bool:
        """Breadcrumb path string'ine göre drill — bulunursa True."""
        if not self.current_node:
            return False
        target_path = target_path.rstrip("/") or "/"
        for h in self.history:
            if h.path.rstrip("/") == target_path:
                self.drill_to(h)
                return True
        return False

    # ---- Queries ----

    def hit_test(self, x: float, y: float) -> Optional[TreeNode]:
        """Görsel mod'a göre hit test. View tıklama event'inde çağırır."""
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
                path, cancel=self._cancel_event, progress=progress
            )
        except Exception as e:
            self.on_error(_("Disk map error: {err}").format(err=e))
            node = None
        self._scan_done(node, path)

    def _scan_done(self, node: Optional[TreeNode], path: str) -> None:
        self._set_busy(False)
        if node is None:
            self.on_progress(_("Scan cancelled or errored."))
            self.on_log(_("Disk map cancelled/errored.") + "\n")
            events.emit("treemap.scan.finished", path=path, ok=False)
            return
        self.root_node = node
        self.current_node = node
        self.history = []
        self.on_root_loaded(node)
        self.on_current_changed(node, self.history)
        self.on_log(
            _("Disk map ready: total {size}").format(size=human(node.size)) + "\n"
        )
        events.emit(
            "treemap.scan.finished",
            path=node.path, size=node.size, ok=True,
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.on_busy_changed(busy)


def _noop(*_a, **_kw) -> None:
    pass


def _noop2(*_a, **_kw) -> None:
    pass


__all__ = ["TreemapController"]
