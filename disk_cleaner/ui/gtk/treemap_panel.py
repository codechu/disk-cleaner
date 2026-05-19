"""TreemapPanel — disk-map View (Gtk).

The state machine is owned by
:class:`~disk_cleaner.controllers.treemap.TreemapController`; this
class is responsible only for:

- Widget setup (toolbar, breadcrumb, DrawingArea)
- Cairo drawing (treemap rects + sunburst arcs + curved text)
- Hover state and drill-transition fade animation (UI animation)
- PNG export dialog
- Controller observer wiring

The callbacks the controller invokes may come from worker threads, so
each one is wrapped with ``GLib.idle_add``.
"""

from __future__ import annotations

import colorsys
import math
import os
import time
from collections.abc import Callable

from ..._gtk import Gdk, GLib, Gtk, Pango
from ...controllers import TreemapController
from ...i18n import _, ngettext
from ...theme import is_dark_theme
from ...utils import human
from ...viz import (
    TreeNode,
    is_hash_like,
    layout_sunburst,
    layout_treemap,
    node_color,
)


def _node_color_themed(
    top_idx: int, depth: int, is_other: bool = False
) -> tuple[float, float, float]:
    """Theme-aware wrapper over ``viz.node_color``."""
    return node_color(top_idx, depth, dark=is_dark_theme(), is_other=is_other)


def _idle(fn: Callable) -> Callable:
    """Marshal a callback from a worker thread onto the Gtk main thread."""

    def wrapper(*args, **kwargs):
        GLib.idle_add(lambda: (fn(*args, **kwargs), False)[1])

    return wrapper


class TreemapPanel(Gtk.Box):
    def __init__(self, win, controller: TreemapController | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_border_width(6)
        self.win = win
        self.controller: TreemapController = controller or TreemapController()

        # View-local state (controller'a ait olmayan)
        self._hover_node: TreeNode | None = None
        self._hover_center = False
        self._fade_alpha = 1.0
        self._fade_dir = 0  # -1: out, +1: in, 0: idle
        self._pending_commit: Callable[[], None] | None = None

        # ---- Toolbar ----
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(bar, False, False, 0)
        bar.pack_start(Gtk.Label(label=_("Path:"), xalign=0), False, False, 0)
        self.entry = Gtk.Entry()
        self.entry.set_text(self.controller.path)
        self.entry.set_hexpand(True)
        self.entry.connect("changed", lambda *_: self.controller.set_path(self.entry.get_text()))
        bar.pack_start(self.entry, True, True, 0)

        self.scan_btn = Gtk.Button(label=_("🔍 Scan"))
        self.scan_btn.connect("clicked", lambda *_: self.controller.start_scan())
        bar.pack_start(self.scan_btn, False, False, 0)

        self.up_btn = Gtk.Button(label=_("⬆ Up"))
        self.up_btn.connect("clicked", lambda *_: self._begin_drill(self.controller.drill_up))
        self.up_btn.set_sensitive(False)
        bar.pack_start(self.up_btn, False, False, 0)

        self.png_btn = Gtk.Button(label=_("📤 PNG"))
        self.png_btn.set_tooltip_text(_("Save current visualization as PNG"))
        self.png_btn.connect("clicked", self.on_export_png)
        self.png_btn.set_sensitive(False)
        bar.pack_start(self.png_btn, False, False, 0)

        self.viz_combo = Gtk.ComboBoxText()
        self.viz_combo.append("treemap", _("🟦 Treemap"))
        self.viz_combo.append("sunburst", _("🌅 Sunburst"))
        self.viz_combo.set_active_id(self.controller.viz_mode)
        self.viz_combo.connect(
            "changed",
            lambda c: (
                self.controller.set_viz_mode(c.get_active_id()),
                self.area.queue_draw(),
            )[1],
        )
        bar.pack_start(self.viz_combo, False, False, 0)

        self.cancel_btn = Gtk.Button(label=_("⛔ Cancel"))
        self.cancel_btn.connect("clicked", lambda *_: self.controller.cancel())
        self.cancel_btn.set_no_show_all(True)
        bar.pack_start(self.cancel_btn, False, False, 0)

        self.spinner = Gtk.Spinner()
        self.spinner.set_no_show_all(True)
        bar.pack_start(self.spinner, False, False, 0)

        # ---- Breadcrumb ----
        crumb_scroll = Gtk.ScrolledWindow()
        crumb_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        crumb_scroll.set_min_content_height(28)
        self.pack_start(crumb_scroll, False, False, 0)
        self.crumb_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        crumb_scroll.add(self.crumb_box)

        # ---- DrawingArea ----
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(-1, 200)
        self.area.set_hexpand(True)
        self.area.set_vexpand(True)
        self.area.connect("draw", self.on_draw)
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        self.area.connect("button-press-event", self.on_click)
        self.area.connect("motion-notify-event", self.on_motion)
        self.pack_start(self.area, True, True, 0)

        hint = Gtk.Label(xalign=0)
        hint.set_markup(
            _(
                "<i>Each colored block is a child of the current folder. "
                "Size = disk size. "
                "<b>Click</b> a folder → drill in. "
                "<b>Right-click</b> or ⬆ Up → go up.</i>"
            )
        )
        hint.set_line_wrap(True)
        self.pack_start(hint, False, False, 0)

        self.info = Gtk.Label(xalign=0)
        self.info.set_use_markup(True)
        self.info.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.pack_start(self.info, False, False, 0)

        # ---- Controller observer wiring (thread-safe) ----
        c = self.controller
        c.on_busy_changed = _idle(self._on_busy_changed)
        c.on_root_loaded = _idle(self._on_root_loaded)
        c.on_current_changed = _idle(self._on_current_changed)
        c.on_viz_mode_changed = _idle(lambda _m: self.area.queue_draw())
        c.on_progress = _idle(self._set_crumb_text)
        c.on_log = _idle(self.win.log)
        c.on_error = _idle(self.win.log)

    # ---- Public helpers (legacy API surface) ----

    def set_default_path(self, path: str) -> None:
        self.entry.set_text(path)
        self.controller.set_path(path)

    # ---- Observer reactions (invoked on the Gtk main thread) ----

    def _on_busy_changed(self, busy: bool) -> None:
        self.scan_btn.set_sensitive(not busy)
        if busy:
            self.cancel_btn.show()
            self.spinner.show()
            self.spinner.start()
            self._set_crumb_text(_("Scanning: {path}").format(path=self.controller.path))
        else:
            self.cancel_btn.hide()
            self.spinner.stop()
            self.spinner.hide()

    def _on_root_loaded(self, _node: TreeNode) -> None:
        self.png_btn.set_sensitive(True)

    def _on_current_changed(self, current: TreeNode, history: list[TreeNode]) -> None:
        self.up_btn.set_sensitive(bool(history))
        self.entry.set_text(current.path)
        self._update_crumb()
        self.area.queue_draw()

    # ---- Breadcrumb ----

    def _set_crumb_text(self, text: str) -> None:
        for c in list(self.crumb_box.get_children()):
            self.crumb_box.remove(c)
        lbl = Gtk.Label(label=text, xalign=0)
        lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.crumb_box.pack_start(lbl, True, True, 0)
        self.crumb_box.show_all()

    def _update_crumb(self) -> None:
        for c in list(self.crumb_box.get_children()):
            self.crumb_box.remove(c)
        n = self.controller.current_node
        if not n:
            return
        path = n.path.rstrip("/") or "/"
        parts = path.split("/")
        if parts[0] == "":
            parts[0] = "/"
        cum = ""
        for i, part in enumerate(parts):
            if i > 0:
                sep = Gtk.Label(label="›")
                sep.get_style_context().add_class("dim-label")
                self.crumb_box.pack_start(sep, False, False, 2)
            if part == "/":
                cum = "/"
                label = "/"
            else:
                cum = (cum.rstrip("/") + "/" + part) if cum else part
                label = part
            btn = Gtk.Button(label=label)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_can_focus(False)
            btn.set_tooltip_text(cum)
            if i == len(parts) - 1:
                btn.set_sensitive(False)
                lbl = btn.get_child()
                if isinstance(lbl, Gtk.Label):
                    lbl.set_markup(f"<b>{GLib.markup_escape_text(label)}</b>")
            else:
                btn.connect("clicked", self._on_crumb_clicked, cum)
            self.crumb_box.pack_start(btn, False, False, 0)
        size_lbl = Gtk.Label()
        size_lbl.set_markup(f"  <span foreground='#888'>— {human(n.size)}</span>")
        self.crumb_box.pack_start(size_lbl, False, False, 0)
        self.crumb_box.show_all()

    def _on_crumb_clicked(self, _btn, target_path: str) -> None:
        if self._fade_dir != 0:
            return

        def commit() -> None:
            if not self.controller.drill_to_path(target_path):
                self.entry.set_text(target_path)
                self.win.log(_("Path: {path} (press Scan)\n").format(path=target_path))

        self._begin_drill(commit)

    # ---- Fade animation (view-only) ----

    def _begin_drill(self, commit: Callable[[], None]) -> None:
        """Start fade-out; commit() is called on completion → controller state mutation."""
        if self._fade_dir != 0:
            return
        self._pending_commit = commit
        self._fade_dir = -1
        GLib.timeout_add(16, self._fade_step)

    def _fade_step(self) -> bool:
        self._fade_alpha += self._fade_dir * 0.18
        if self._fade_dir < 0 and self._fade_alpha <= 0.0:
            self._fade_alpha = 0.0
            if self._pending_commit is not None:
                commit = self._pending_commit
                self._pending_commit = None
                commit()
            self._fade_dir = +1
        elif self._fade_dir > 0 and self._fade_alpha >= 1.0:
            self._fade_alpha = 1.0
            self._fade_dir = 0
            self.area.queue_draw()
            return False
        self.area.queue_draw()
        return True

    # ---- Click + hover ----

    def _is_center_click(self, x: float, y: float) -> bool:
        if self.controller.viz_mode != "sunburst" or not self.controller.current_node:
            return False
        alloc = self.area.get_allocation()
        cx, cy = alloc.width / 2, alloc.height / 2
        r_step = (min(alloc.width, alloc.height) / 2 - 24) / 6
        dx, dy = x - cx, y - cy
        return (dx * dx + dy * dy) ** 0.5 < r_step

    def on_click(self, _w, event) -> bool:
        if not self.controller.current_node:
            return False
        if event.button == 3:
            self._begin_drill(self.controller.drill_up)
            return True
        if self._is_center_click(event.x, event.y):
            self._begin_drill(self.controller.drill_up)
            return True
        hit = self.controller.hit_test(event.x, event.y)
        if hit and hit.is_dir and hit is not self.controller.current_node and self._fade_dir == 0:
            self._begin_drill(lambda: self.controller.drill_in(hit))
        return True

    def on_motion(self, _w, event) -> bool:
        if not self.controller.current_node:
            return False
        prev_hover = self._hover_node
        prev_center = self._hover_center
        self._hover_center = self._is_center_click(event.x, event.y)
        hit = self.controller.hit_test(event.x, event.y)
        self._hover_node = hit
        if hit:
            self.info.set_markup(self._format_hover(hit))
        if prev_hover is not self._hover_node or prev_center != self._hover_center:
            self.area.queue_draw()
        return False

    def _format_hover(self, node: TreeNode) -> str:
        parts = [
            f"<b>{GLib.markup_escape_text(node.path)}</b>",
            f"<tt>{human(node.size)}</tt>",
        ]
        cur = self.controller.current_node
        if cur and cur.size > 0:
            pct = node.size / cur.size * 100
            parts.append(f"<span color='#888'>%{pct:.1f}</span>")
        try:
            if node.is_dir:
                child_text = ngettext(
                    "{n} child",
                    "{n} children",
                    len(node.children),
                ).format(n=len(node.children))
                parts.append(f"<span color='#888'>{GLib.markup_escape_text(child_text)}</span>")
        except Exception:
            pass
        try:
            mt = os.path.getmtime(node.path)
            age = int((time.time() - mt) / 86400)
            if age > 0:
                ago_text = ngettext(
                    "{n} day ago",
                    "{n} days ago",
                    age,
                ).format(n=age)
                parts.append(f"<span color='#888'>{GLib.markup_escape_text(ago_text)}</span>")
        except Exception:
            pass
        return "  ·  ".join(parts)

    # ---- PNG export ----

    def on_export_png(self, _b) -> None:
        cur = self.controller.current_node
        if not cur:
            return
        dlg = Gtk.FileChooserDialog(
            title=_("Save treemap as PNG"),
            parent=self.win,
            action=Gtk.FileChooserAction.SAVE,
        )
        dlg.add_buttons(
            _("Cancel"),
            Gtk.ResponseType.CANCEL,
            _("Save"),
            Gtk.ResponseType.ACCEPT,
        )
        dlg.set_do_overwrite_confirmation(True)
        ts = time.strftime("%Y-%m-%d_%H-%M")
        base = os.path.basename(cur.path.rstrip("/")) or "root"
        dlg.set_current_name(f"treemap_{base}_{ts}.png")
        resp = dlg.run()
        target = dlg.get_filename() if resp == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if not target:
            return
        if not target.lower().endswith(".png"):
            target += ".png"
        try:
            import cairo as _cairo

            alloc = self.area.get_allocation()
            w, h = max(800, alloc.width), max(600, alloc.height)
            surface = _cairo.ImageSurface(_cairo.FORMAT_ARGB32, w, h)
            cr = _cairo.Context(surface)
            cr.set_source_rgb(1, 1, 1)
            cr.rectangle(0, 0, w, h)
            cr.fill()
            if self.controller.viz_mode == "sunburst":
                self._draw_sunburst(cr, w, h)
            else:
                layout_treemap(cur, 0, 0, w, h)
                for i, c in enumerate(cur.children):
                    self._draw_child(cr, c, i)
            cr.set_source_rgb(0, 0, 0)
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(14)
            cr.move_to(8, 18)
            cr.show_text(f"{cur.path}  —  {human(cur.size)}")
            surface.write_to_png(target)
            self.win.log(_("✓ PNG saved: {target}\n").format(target=target))
        except Exception as e:
            self.win.log(_("✗ PNG save error: {err}\n").format(err=e))

    # ---- Cairo draw ----

    def on_draw(self, _w, cr) -> bool:
        try:
            cr.set_source_rgb(1, 1, 1)
        except (TypeError, AttributeError):
            return False
        alloc = self.area.get_allocation()
        w, h = alloc.width, alloc.height
        dark = is_dark_theme()
        if dark:
            cr.set_source_rgb(0.18, 0.18, 0.20)
        else:
            cr.set_source_rgb(0.97, 0.97, 0.97)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        fading = self._fade_dir != 0
        if fading:
            cr.push_group()
        try:
            self._draw_content(cr, w, h, dark)
        finally:
            if fading:
                cr.pop_group_to_source()
                cr.paint_with_alpha(max(0.0, min(1.0, self._fade_alpha)))
        return False

    def _draw_content(self, cr, w: float, h: float, dark: bool) -> bool:
        cur = self.controller.current_node
        if not cur:
            cr.set_source_rgb(0.65, 0.65, 0.65) if dark else cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.select_font_face("Sans")
            cr.set_font_size(18)
            msg = _("Enter a path and press Scan")
            ext = cr.text_extents(msg)
            cr.move_to((w - ext.width) / 2, h / 2)
            cr.show_text(msg)
            cr.set_font_size(11)
            cr.set_source_rgb(0.55, 0.55, 0.55) if dark else cr.set_source_rgb(0.6, 0.6, 0.6)
            hint = _("Each folder is drawn as a block proportional to its size. Click to drill in.")
            ext2 = cr.text_extents(hint)
            cr.move_to((w - ext2.width) / 2, h / 2 + 24)
            cr.show_text(hint)
            return False
        if cur.size == 0 or not cur.children:
            cr.set_source_rgb(0.3, 0.3, 0.3)
            cr.select_font_face("Sans")
            cr.set_font_size(14)
            cr.move_to(20, 30)
            cr.show_text(_("(empty folder)"))
            return False
        if self.controller.viz_mode == "sunburst":
            self._draw_sunburst(cr, w, h)
        else:
            layout_treemap(cur, 0, 0, w, h)
            for i, c in enumerate(cur.children):
                self._draw_child(cr, c, i)
        return False

    def _draw_sunburst(self, cr, w: float, h: float) -> None:
        cur = self.controller.current_node
        if not cur:
            return
        cx, cy = w / 2, h / 2
        pad = max(30, min(120, int(min(w, h) * 0.10)))
        max_r = max(50, min(w, h) / 2 - pad)
        depth_max = 3
        r_step = max_r / (depth_max + 1)
        self._clear_rects(cur)
        layout_sunburst(cur, cx, cy, r_step, r_step, max_depth=depth_max)
        all_arcs: list[tuple[TreeNode, int]] = []
        self._collect_arcs(cur, all_arcs, depth=0)
        for arc in all_arcs:
            self._draw_arc(cr, arc)
        self._draw_center(cr, cx, cy, r_step)

    def _clear_rects(self, node: TreeNode) -> None:
        node.rect = None
        for c in node.children:
            self._clear_rects(c)

    def _collect_arcs(
        self,
        node: TreeNode,
        out: list[tuple[TreeNode, int]],
        depth: int,
        max_depth: int = 3,
    ) -> None:
        if depth > max_depth:
            return
        if depth > 0:
            out.append((node, depth))
        for c in node.children:
            self._collect_arcs(c, out, depth + 1, max_depth)

    def _draw_arc(self, cr, arc: tuple[TreeNode, int]) -> None:
        node, depth = arc
        if node.rect is None:
            return
        cx, cy, r_in, r_out, a0, a1, top_idx = node.rect
        span = a1 - a0
        if span < 0.005:
            return
        is_hover = self._hover_node is node
        is_other = node.is_other
        r, g, b = _node_color_themed(top_idx, depth, is_other=is_other)
        if is_hover:
            mult = 1.18 if is_dark_theme() else 1.25
            r, g, b = min(1, r * mult), min(1, g * mult), min(1, b * mult)
        cr.set_source_rgb(r, g, b)
        cr.new_path()
        cr.arc(cx, cy, r_out, a0, a1)
        cr.arc_negative(cx, cy, r_in, a1, a0)
        cr.close_path()
        cr.fill_preserve()
        dark = is_dark_theme()
        if is_hover:
            if dark:
                cr.set_source_rgba(1, 1, 1, 0.55)
            else:
                cr.set_source_rgba(0, 0, 0, 0.55)
            cr.set_line_width(1.8)
        else:
            if dark:
                cr.set_source_rgba(0, 0, 0, 0.40)
            else:
                cr.set_source_rgba(1, 1, 1, 0.55)
            cr.set_line_width(0.8)
        cr.stroke()
        arc_pixels = span * (r_in + r_out) / 2
        ring_h = r_out - r_in
        if arc_pixels > 40 and ring_h > 16:
            self._draw_arc_label(cr, node, cx, cy, r_in, r_out, a0, a1)

    def _draw_arc_label(self, cr, node, cx, cy, r_in, r_out, a0, a1) -> None:
        if node.is_other:
            name = (
                _("Other")
                + " "
                + ngettext("({n} item)", "({n} items)", node.small_count).format(n=node.small_count)
            )
        else:
            name = os.path.basename(node.path) or node.path
        if is_hash_like(name):
            return
        if len(name) > 28:
            name = name[:25] + "…"
        ring_h = r_out - r_in
        radius = r_in + ring_h * 0.42
        mid_angle = (a0 + a1) / 2
        arc_pixels = (a1 - a0) * radius
        budget = arc_pixels * 0.85
        cr.set_source_rgb(0.08, 0.08, 0.08)
        cr.select_font_face("Sans")

        max_font = min(ring_h * 0.42, 18)
        base_font = max(8, min(13, ring_h * 0.38))
        cr.set_font_size(base_font)
        text_w = sum(cr.text_extents(ch).x_advance for ch in name)
        if text_w > 0 and text_w < budget * 0.7:
            scale = min(budget * 0.85 / text_w, max_font / base_font)
            font_size = base_font * scale
        elif text_w > budget:
            font_size = base_font
            while len(name) > 2:
                test = name + "…"
                w = sum(cr.text_extents(ch).x_advance for ch in test)
                if w <= budget:
                    name = test
                    break
                name = name[:-1]
            if len(name) <= 2:
                return
        else:
            font_size = base_font
        cr.set_font_size(font_size)
        self._draw_curved_text(cr, name, cx, cy, radius, mid_angle, font_size)

    def _draw_curved_text(self, cr, text, cx, cy, radius, mid_angle, font_size) -> None:
        char_widths = [cr.text_extents(ch).x_advance for ch in text]
        total_w = sum(char_widths)
        total_arc = total_w / radius if radius > 0 else 0
        is_top = math.sin(mid_angle) < 0

        if is_top:
            cur = mid_angle - total_arc / 2
            for ch, adv in zip(text, char_widths, strict=False):
                ch_arc = adv / radius
                ch_mid = cur + ch_arc / 2
                cr.save()
                cr.translate(cx, cy)
                cr.rotate(ch_mid)
                cr.translate(radius, 0)
                cr.rotate(math.pi / 2)
                cr.move_to(-adv / 2, font_size * 0.32)
                cr.show_text(ch)
                cr.restore()
                cur += ch_arc
        else:
            cur = mid_angle + total_arc / 2
            for ch, adv in zip(text, char_widths, strict=False):
                ch_arc = adv / radius
                ch_mid = cur - ch_arc / 2
                cr.save()
                cr.translate(cx, cy)
                cr.rotate(ch_mid)
                cr.translate(radius, 0)
                cr.rotate(-math.pi / 2)
                cr.move_to(-adv / 2, font_size * 0.32)
                cr.show_text(ch)
                cr.restore()
                cur -= ch_arc

    def _draw_center(self, cr, cx, cy, r) -> None:
        dark = is_dark_theme()
        cur = self.controller.current_node
        has_history = self.controller.can_go_up
        is_hover = self._hover_center or (self._hover_node is cur)
        if dark:
            if has_history:
                base = 0.30 if not is_hover else 0.38
                cr.set_source_rgb(base, base, base + 0.05)
            else:
                base = 0.26 if not is_hover else 0.32
                cr.set_source_rgb(base, base, base)
        else:
            if has_history:
                base = 0.92 if not is_hover else 0.85
                cr.set_source_rgb(base, base, 0.98)
            else:
                base = 0.96 if not is_hover else 0.90
                cr.set_source_rgb(base, base, base)
        cr.arc(cx, cy, r * 0.95, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(0.7, 0.7, 0.7, 0.4) if dark else cr.set_source_rgba(0.3, 0.3, 0.3, 0.4)
        cr.set_line_width(1)
        cr.arc(cx, cy, r * 0.95, 0, 2 * math.pi)
        cr.stroke()
        if cur is None:
            return
        name = os.path.basename(cur.path.rstrip("/")) or cur.path
        if len(name) > 16:
            name = name[:14] + "…"
        cr.set_source_rgb(0.90, 0.90, 0.90) if dark else cr.set_source_rgb(0.15, 0.15, 0.15)
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(12)
        ext = cr.text_extents(name)
        cr.move_to(cx - ext.width / 2, cy - 4)
        cr.show_text(name)
        cr.select_font_face("Sans", 0, 0)
        cr.set_font_size(10)
        size_text = human(cur.size)
        ext = cr.text_extents(size_text)
        cr.move_to(cx - ext.width / 2, cy + 10)
        cr.show_text(size_text)
        if has_history:
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(8)
            up = _("up")
            ext = cr.text_extents(up)
            cr.move_to(cx - ext.width / 2, cy + 22)
            cr.set_source_rgb(0.5, 0.5, 0.65)
            cr.show_text(up)

    def _draw_child(self, cr, node: TreeNode, idx: int) -> None:
        if node.rect is None:
            return
        x, y, w, h = node.rect
        if w < 2 or h < 2:
            return
        dark = is_dark_theme()
        is_hover = self._hover_node is node
        is_other = node.is_other
        if is_other:
            v = 0.38 if dark else 0.80
            if is_hover:
                v += 0.08 if dark else 0.06
            r, g, b = v, v, v
        else:
            hue = (idx * 0.618 + 0.08) % 1.0
            if dark:
                # pastel-on-dark
                light = 0.52
                sat = 0.28
            else:
                # vivid-on-light
                light = 0.60
                sat = 0.82
            if is_hover:
                if dark:
                    light = min(0.66, light + 0.10)
                    sat = min(0.42, sat + 0.10)
                else:
                    light = min(0.72, light + 0.08)
                    sat = min(0.95, sat + 0.10)
            r, g, b = colorsys.hls_to_rgb(hue, light, sat)
        cr.set_source_rgb(r, g, b)
        cr.rectangle(x, y, w, h)
        cr.fill()
        if is_hover:
            if dark:
                cr.set_source_rgba(1, 1, 1, 0.55)
            else:
                cr.set_source_rgba(0, 0, 0, 0.55)
            cr.set_line_width(2)
            cr.rectangle(x + 1, y + 1, w - 2, h - 2)
            cr.stroke()
        else:
            if dark:
                cr.set_source_rgba(0, 0, 0, 0.30)
            else:
                cr.set_source_rgba(1, 1, 1, 0.55)
            cr.set_line_width(1)
            cr.rectangle(x + 0.5, y + 0.5, w - 1, h - 1)
            cr.stroke()
        if w > 60 and h > 24:
            if is_other:
                name = (
                    _("Other")
                    + " "
                    + ngettext("({n} item)", "({n} items)", node.small_count).format(
                        n=node.small_count
                    )
                )
            else:
                name = os.path.basename(node.path) or node.path
            size_str = human(node.size)
            cr.set_source_rgb(0.1, 0.1, 0.1)
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(min(13, max(9, h / 6)))
            cr.move_to(x + 6, y + 16)
            max_chars = max(6, int(w / 8))
            short = name if len(name) <= max_chars else name[: max_chars - 1] + "…"
            cr.show_text(short)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(min(11, max(8, h / 8)))
            cr.move_to(x + 6, y + 32)
            cr.show_text(size_str)

    # ---- Backward compatibility (attributes read by the control API) ----

    @property
    def current_node(self) -> TreeNode | None:
        return self.controller.current_node

    @property
    def root_node(self) -> TreeNode | None:
        return self.controller.root_node

    @property
    def history(self) -> list[TreeNode]:
        return self.controller.history

    @property
    def viz_mode(self) -> str:
        return self.controller.viz_mode

    @property
    def _busy(self) -> bool:
        return self.controller.busy


__all__ = ["TreemapPanel"]
