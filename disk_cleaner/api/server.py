# SPDX-License-Identifier: GPL-3.0-or-later

"""Control API — JSON-line command server over a Unix socket.

Socket path: ``$XDG_RUNTIME_DIR/disk_cleaner/control.sock``
(see :mod:`disk_cleaner.config`). Each connection runs on its own
thread; ``cmd`` is executed on the main thread via ``GLib.idle_add``
(Gtk is not thread-safe).

**Security:** ``clean`` and every target considered destructive is
BLOCKED from the API. Only the user can trigger them manually via the
GUI. To extend ``_DESTRUCTIVE_TARGETS``: add a target whose user data
cannot be recovered.
"""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

from codechu_events import DEFAULT_HEARTBEAT_SEC, SubscriberLimitExceeded

from .._bus import bus
from .._gtk import Gdk, GLib, Gtk
from ..config import CONTROL_SOCKET as _CONTROL_SOCKET_PATH
from ..i18n import _
from ..settings import SETTINGS

CONTROL_SOCKET: Path = Path(_CONTROL_SOCKET_PATH)


class ControlServer:
    """JSON-line socket server. Every command runs on the main thread."""

    # Commands considered destructive — NEVER triggered via the API.
    # No deletion flow may start without explicit, manual user approval.
    _DESTRUCTIVE_TARGETS: frozenset[str] = frozenset({"clean"})

    def __init__(self, win) -> None:
        self.win = win
        self.sock_path = CONTROL_SOCKET
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        try:
            if self.sock_path.exists():
                self.sock_path.unlink()
        except OSError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(self.sock_path))
        sock.listen(4)
        self._server = sock
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.win.log(_("Control socket: {path}\n").format(path=self.sock_path))

    def _loop(self) -> None:
        while True:
            try:
                conn, _ = self._server.accept()
            except Exception:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn) -> None:
        try:
            f = conn.makefile("rwb", buffering=0)
            for raw in f:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception as e:
                    self._send(f, {"ok": False, "error": f"json: {e}"})
                    continue

                # subscribe: switch the connection to push mode and keep
                # it alive until conn is closed. After subscribe, no
                # further cmd is accepted on the same connection (terminal).
                if msg.get("cmd") == "subscribe":
                    self._stream_subscribe(f, msg)
                    return

                result_holder: dict = {}
                done = threading.Event()

                def runner(
                    msg=msg, result_holder=result_holder, done=done
                ) -> bool:
                    try:
                        result_holder["v"] = self._dispatch(msg)
                    except Exception as e:
                        result_holder["v"] = {"ok": False, "error": str(e)}
                    done.set()
                    return False

                GLib.idle_add(runner)
                if done.wait(timeout=60):
                    self._send(
                        f,
                        result_holder.get("v", {"ok": False, "error": "timeout"}),
                    )
                else:
                    self._send(f, {"ok": False, "error": "timeout"})
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _stream_subscribe(self, f, msg: dict) -> None:
        """Event bus → push to this connection.

        Message fields:

        - ``types`` (opt): glob list, default ``["*"]``.
        - ``heartbeat_sec`` (opt): default 5.0; 0 disables it.

        One-way push runs until the connection is closed; exit silently
        on broken pipe.
        """
        types = msg.get("types") or ["*"]
        hb = float(msg.get("heartbeat_sec", DEFAULT_HEARTBEAT_SEC))
        try:
            sub = bus.subscribe(types, heartbeat_sec=hb)
        except SubscriberLimitExceeded as e:
            self._send(f, {"ok": False, "error": f"limit: {e}"})
            return
        # Welcome event: subscription ack + filter echo
        self._send(
            f,
            {
                "ok": True,
                "subscribed": types,
                "heartbeat_sec": hb,
            },
        )
        try:
            for event in sub.iter(heartbeat=hb > 0):
                self._send(f, event)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            bus.unsubscribe(sub)

    def _send(self, f, obj: dict) -> None:
        try:
            f.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())
        except Exception:
            pass

    # ---- command dispatcher ----

    def _dispatch(self, msg: dict) -> dict:
        cmd = msg.get("cmd")
        if cmd == "screenshot":
            return self._cmd_screenshot(msg)
        if cmd == "list_tabs":
            return self._cmd_list_tabs()
        if cmd == "set_tab":
            return self._cmd_set_tab(msg)
        if cmd == "list_cleanup_modes":
            return self._cmd_list_cleanup_modes()
        if cmd == "select_cleanup_mode":
            return self._cmd_select_cleanup_mode(msg)
        if cmd == "click":
            return self._cmd_click(msg)
        if cmd == "set_entry":
            return self._cmd_set_entry(msg)
        if cmd == "get_state":
            return self._cmd_get_state()
        if cmd == "set_check":
            return self._cmd_set_check(msg)
        if cmd == "click_at":
            return self._cmd_click_at(msg)
        if cmd == "mouse_move":
            return self._cmd_mouse_move(msg)
        if cmd == "exit":
            GLib.idle_add(Gtk.main_quit)
            return {"ok": True}
        if cmd == "window":
            return self._cmd_window(msg)
        if cmd == "debug":
            return self._cmd_debug(msg)
        return {"ok": False, "error": _("unknown cmd: {cmd}").format(cmd=cmd)}

    def _cmd_screenshot(self, msg: dict) -> dict:
        from ..config import RUNTIME_DIR

        default_path = str(RUNTIME_DIR / "screenshot.png")
        path = msg.get("path", default_path)
        try:
            import cairo as _cairo

            alloc = self.win.get_allocation()
            w, h = max(100, alloc.width), max(100, alloc.height)
            surface = _cairo.ImageSurface(_cairo.FORMAT_ARGB32, w, h)
            cr = _cairo.Context(surface)
            cr.set_source_rgb(1, 1, 1)
            cr.paint()
            self.win.draw(cr)
            surface.write_to_png(path)
            return {"ok": True, "path": path, "size": [w, h]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _notebook(self):
        """First Gtk.Notebook among the children of MainWindow.outer."""
        for child in self.win.get_children():
            if isinstance(child, Gtk.Box):
                for c in child.get_children():
                    if isinstance(c, Gtk.Notebook):
                        return c
        return None

    def _cmd_list_tabs(self) -> dict:
        nb = self._notebook()
        if not nb:
            return {"ok": False, "error": _("no notebook")}
        tabs = []
        for i in range(nb.get_n_pages()):
            page = nb.get_nth_page(i)
            label = nb.get_tab_label(page)
            text = label.get_text() if isinstance(label, Gtk.Label) else f"tab{i}"
            tabs.append({"index": i, "label": text})
        return {"ok": True, "tabs": tabs, "current": nb.get_current_page()}

    def _cmd_set_tab(self, msg: dict) -> dict:
        nb = self._notebook()
        if not nb:
            return {"ok": False, "error": _("no notebook")}
        if "index" in msg:
            nb.set_current_page(int(msg["index"]))
            return {"ok": True}
        name = msg.get("name", "")
        for i in range(nb.get_n_pages()):
            page = nb.get_nth_page(i)
            label = nb.get_tab_label(page)
            text = label.get_text() if isinstance(label, Gtk.Label) else ""
            if name.lower() in text.lower():
                nb.set_current_page(i)
                return {"ok": True, "set": text}
        return {"ok": False, "error": _("tab not found: {name}").format(name=name)}

    def _cmd_list_cleanup_modes(self) -> dict:
        out = []
        model = self.win.cleanup_combo.get_model()
        for row in model:
            out.append({"id": row[1], "label": row[0]})
        return {
            "ok": True,
            "modes": out,
            "current": self.win.cleanup_combo.get_active_id(),
        }

    def _cmd_select_cleanup_mode(self, msg: dict) -> dict:
        self.win.cleanup_combo.set_active_id(msg.get("id", "sys"))
        return {"ok": True}

    def _cmd_click(self, msg: dict) -> dict:
        """Targets: ``scan`` / ``cancel`` / ``select_all`` / ``select_none`` /
        ``export`` / ``png`` / ``up``. ``clean`` is BLOCKED via the API."""
        target = msg.get("target", "scan")
        if target in self._DESTRUCTIVE_TARGETS:
            return {
                "ok": False,
                "error": _(
                    "'{target}' blocked via API — destructive operations "
                    "can only be triggered manually by the user"
                ).format(target=target),
            }
        panel_id = msg.get("panel", "suggestion")
        panel = self._resolve_panel(panel_id)
        if panel is None:
            return {"ok": False, "error": _("no panel: {pid}").format(pid=panel_id)}
        btn_map = {
            "scan": "scan_btn",
            "cancel": "cancel_btn",
            "select_all": "all_btn",
            "select_none": "none_btn",
            "export": "export_btn",
            "png": "png_btn",
            "up": "up_btn",
        }
        attr = btn_map.get(target)
        if attr and hasattr(panel, attr):
            getattr(panel, attr).clicked()
            return {"ok": True}
        return {"ok": False, "error": _("no button or blocked: {target}").format(target=target)}

    def _resolve_panel(self, pid: str):
        if pid == "suggestion":
            return self.win.suggestion_panel
        if pid == "treemap":
            return self.win.treemap_panel
        if pid == "current_cleanup":
            current = self.win.cleanup_combo.get_active_id()
            return self.win.cleanup_stack.get_child_by_name(current)
        return self.win._panels_by_key.get(pid)

    def _cmd_set_entry(self, msg: dict) -> dict:
        pid = msg.get("panel")
        value = msg.get("value", "")
        panel = self._resolve_panel(pid)
        if panel and hasattr(panel, "entry"):
            panel.entry.set_text(value)
            return {"ok": True}
        if panel and hasattr(panel, "set_default_path"):
            panel.set_default_path(value)
            return {"ok": True}
        return {"ok": False, "error": _("no entry: {pid}").format(pid=pid)}

    def _cmd_set_check(self, msg: dict) -> dict:
        chk = msg.get("name")
        val = bool(msg.get("value", True))
        if chk == "trash":
            self.win.trash_chk.set_active(val)
            return {"ok": True}
        if chk == "dry_run":
            self.win.dry_chk.set_active(val)
            return {"ok": True}
        return {"ok": False, "error": _("no checkbox: {name}").format(name=chk)}

    def _cmd_click_at(self, msg: dict) -> dict:
        """Coordinate click on cairo render areas (treemap/sunburst, etc.)."""
        x = float(msg.get("x", 0))
        y = float(msg.get("y", 0))
        button = int(msg.get("button", 1))
        target = msg.get("target", "treemap_area")
        widget = self._resolve_widget(target)
        if widget is None:
            return {"ok": False, "error": _("no widget: {target}").format(target=target)}
        ev = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
        ev.button.button = button
        ev.button.x = x
        ev.button.y = y
        ev.button.window = widget.get_window()
        widget.emit("button-press-event", ev)
        return {"ok": True, "at": [x, y], "target": target}

    def _cmd_mouse_move(self, msg: dict) -> dict:
        x = float(msg.get("x", 0))
        y = float(msg.get("y", 0))
        target = msg.get("target", "treemap_area")
        widget = self._resolve_widget(target)
        if widget is None:
            return {"ok": False, "error": _("no widget: {target}").format(target=target)}
        ev = Gdk.Event.new(Gdk.EventType.MOTION_NOTIFY)
        ev.motion.x = x
        ev.motion.y = y
        ev.motion.window = widget.get_window()
        widget.emit("motion-notify-event", ev)
        return {"ok": True}

    def _resolve_widget(self, target: str):
        if target == "treemap_area":
            return self.win.treemap_panel.area
        return None

    def _cmd_debug(self, msg: dict) -> dict:
        """Debug commands: ``treemap_state`` / ``treemap_tree`` / ``redraw`` /
        ``settings`` / ``history`` / ``bus_stats``."""
        target = msg.get("target", "treemap_state")
        if target == "treemap_state":
            tp = self.win.treemap_panel
            cn = tp.current_node
            return {
                "ok": True,
                "state": {
                    "current_path": cn.path if cn else None,
                    "current_size": cn.size if cn else None,
                    "current_rect": list(cn.rect) if cn and cn.rect else None,
                    "viz_mode": tp.viz_mode,
                    "history_depth": len(tp.history),
                    "hover": tp._hover_node.path if tp._hover_node else None,
                    "busy": tp._busy,
                },
            }
        if target == "treemap_tree":
            max_d = int(msg.get("max_depth", 3))
            tp = self.win.treemap_panel
            if not tp.current_node:
                return {"ok": False, "error": _("no current_node")}

            def dump(n, d: int = 0):
                if d > max_d:
                    return None
                return {
                    "path": n.path,
                    "size": n.size,
                    "is_dir": n.is_dir,
                    "rect": list(n.rect) if n.rect else None,
                    "children_count": len(n.children),
                    "children": [
                        dump(c, d + 1) for c in n.children[:30] if dump(c, d + 1) is not None
                    ],
                }

            return {"ok": True, "tree": dump(tp.current_node)}
        if target == "redraw":
            self.win.treemap_panel.area.queue_draw()
            return {"ok": True}
        if target == "settings":
            return {"ok": True, "settings": SETTINGS}
        if target == "history":
            tp = self.win.treemap_panel
            return {
                "ok": True,
                "history_paths": [n.path for n in tp.history],
            }
        if target == "bus_stats":
            return {"ok": True, "stats": bus.stats()}
        return {"ok": False, "error": _("unknown target: {target}").format(target=target)}

    def _cmd_window(self, msg: dict) -> dict:
        action = msg.get("action", "maximize")
        if action == "maximize":
            self.win.maximize()
        elif action == "unmaximize":
            self.win.unmaximize()
        elif action == "resize":
            w = int(msg.get("width", 900))
            h = int(msg.get("height", 620))
            self.win.unmaximize()
            self.win.resize(w, h)
        return {"ok": True, "action": action}

    def _cmd_get_state(self) -> dict:
        nb = self._notebook()
        return {
            "ok": True,
            "state": {
                "tab_index": nb.get_current_page() if nb else -1,
                "trash_mode": self.win.trash_chk.get_active(),
                "dry_run": self.win.dry_chk.get_active(),
                "mount": self.win.mount_combo.get_active_id(),
                "cleanup_mode": self.win.cleanup_combo.get_active_id(),
                "suggestion_busy": self.win.suggestion_panel._busy,
            },
        }


__all__ = ["CONTROL_SOCKET", "ControlServer"]
