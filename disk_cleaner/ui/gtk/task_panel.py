# SPDX-License-Identifier: GPL-3.0-or-later

"""TaskPanel — task-list View (Gtk).

The state machine is owned by
:class:`~disk_cleaner.controllers.TaskListController`; this class is
responsible for:

- Widget setup (toolbar, TreeView + ListStore, action bar, preview)
- Syncing ``Gtk.ListStore`` ↔ controller rows
- The confirmation dialog (the controller calls it via callback)
- :class:`~disk_cleaner.controllers.PreviewResult` → Pango markup
- Thread-safety: every callback runs through the ``_idle()`` wrapper

No scan/clean business logic lives in the View.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from ..._gtk import GLib, Gtk, Pango
from ...controllers import (
    CleanPreview,
    PreviewResult,
    TaskListController,
    TaskRow,
)
from ...i18n import _, ngettext
from ...utils import human
from .widgets import RISK_COLORS


def _idle(fn: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        GLib.idle_add(lambda: (fn(*args, **kwargs), False)[1])

    return wrapper


class TaskPanel(Gtk.Box):
    """Scan/select/clean panel — thin View bound to a controller."""

    # ListStore column indices
    C_CHECK, C_NAME, C_RISK_LABEL, C_RISK_COLOR, C_PATH, C_SIZE_TEXT, C_SIZE_BYTES, C_DESC = range(
        8
    )

    def __init__(
        self,
        win,
        tasks_provider: Callable[..., Iterable[dict[str, Any]]],
        auto_select: bool = True,
        toolbar_extra: Iterable[Gtk.Widget] | None = None,
        hint: str = "",
        name: str = "task",
        controller: TaskListController | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_border_width(6)
        self.win = win
        self.name = name
        self.controller: TaskListController = controller or TaskListController(
            provider=tasks_provider,
            auto_select=auto_select,
            name=name,
        )

        # ---- Toolbar ----
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(bar, False, False, 0)

        if toolbar_extra:
            for w in toolbar_extra:
                bar.pack_start(w, False, False, 0)

        self.scan_btn = Gtk.Button(label=_("🔍  Scan"))
        self.scan_btn.connect("clicked", lambda *_: self.controller.start_scan())
        bar.pack_start(self.scan_btn, False, False, 0)

        self.cancel_btn = Gtk.Button(label="⛔")
        self.cancel_btn.set_tooltip_text(_("Cancel ongoing operation"))
        self.cancel_btn.connect("clicked", lambda *_: self.controller.cancel())
        self.cancel_btn.set_no_show_all(True)
        bar.pack_start(self.cancel_btn, False, False, 0)

        self.spinner = Gtk.Spinner()
        self.spinner.set_no_show_all(True)
        bar.pack_start(self.spinner, False, False, 0)

        self.progress_label = Gtk.Label(xalign=0)
        self.progress_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        bar.pack_start(self.progress_label, True, True, 0)

        if hint:
            self._hint_text = hint
            help_btn = Gtk.Button(label="?")
            help_btn.set_relief(Gtk.ReliefStyle.NONE)
            help_btn.set_tooltip_text(_("What does this panel do?"))
            help_btn.connect("clicked", self._show_hint)
            bar.pack_end(help_btn, False, False, 0)

        # ---- TreeView ----
        self.store = Gtk.ListStore(bool, str, str, str, str, str, "guint64", str)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self.pack_start(scroll, True, True, 0)

        self.tree = Gtk.TreeView(model=self.store)

        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self._on_toggle_widget)
        self.tree.append_column(Gtk.TreeViewColumn("✓", toggle, active=self.C_CHECK))

        col_name = Gtk.TreeViewColumn(_("Task"), Gtk.CellRendererText(), text=self.C_NAME)
        col_name.set_min_width(260)
        col_name.set_resizable(True)
        self.tree.append_column(col_name)

        risk_renderer = Gtk.CellRendererText()
        risk_renderer.set_property("weight", Pango.Weight.BOLD)
        self.tree.append_column(
            Gtk.TreeViewColumn(
                _("Risk"),
                risk_renderer,
                text=self.C_RISK_LABEL,
                foreground=self.C_RISK_COLOR,
            )
        )

        col_path = Gtk.TreeViewColumn(_("Path"), Gtk.CellRendererText(), text=self.C_PATH)
        col_path.set_min_width(260)
        col_path.set_resizable(True)
        self.tree.append_column(col_path)

        size_r = Gtk.CellRendererText()
        size_r.set_property("xalign", 1.0)
        col_size = Gtk.TreeViewColumn(_("Size"), size_r, text=self.C_SIZE_TEXT)
        col_size.set_min_width(90)
        col_size.set_sort_column_id(self.C_SIZE_BYTES)
        self.tree.append_column(col_size)

        self.tree.append_column(
            Gtk.TreeViewColumn(
                _("Description"),
                Gtk.CellRendererText(),
                text=self.C_DESC,
            )
        )
        self.tree.set_tooltip_column(self.C_DESC)

        scroll.add(self.tree)

        # ---- Preview ----
        self.preview_exp = Gtk.Expander(label=_("👁  Preview"))
        self.preview_exp.set_expanded(False)
        self.pack_start(self.preview_exp, False, False, 0)
        self.preview_label = Gtk.Label(xalign=0)
        self.preview_label.set_use_markup(True)
        self.preview_label.set_selectable(True)
        self.preview_label.set_line_wrap(False)
        self.preview_label.set_margin_start(8)
        self.preview_label.set_margin_top(4)
        self.preview_label.set_margin_bottom(4)
        self.preview_label.set_markup(
            "<i>" + GLib.markup_escape_text(_("Select a row to see its contents here.")) + "</i>"
        )
        self.preview_exp.add(self.preview_label)
        self.tree.get_selection().connect("changed", self._on_selection_changed)

        # ---- Action bar ----
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(action_bar, False, False, 0)

        self.total_label = Gtk.Label(xalign=0)
        action_bar.pack_start(self.total_label, True, True, 0)

        self.all_btn = Gtk.Button(label=_("All"))
        self.all_btn.connect("clicked", lambda *_: self.controller.select_all())
        action_bar.pack_start(self.all_btn, False, False, 0)

        self.none_btn = Gtk.Button(label=_("None"))
        self.none_btn.connect("clicked", lambda *_: self.controller.select_none())
        action_bar.pack_start(self.none_btn, False, False, 0)

        self.clean_btn = Gtk.Button(label=_("🧹  Clean"))
        self.clean_btn.get_style_context().add_class("suggested-action")
        self.clean_btn.connect("clicked", lambda *_: self._trigger_clean())
        self.clean_btn.set_sensitive(False)
        action_bar.pack_start(self.clean_btn, False, False, 0)

        # ---- Observer wiring (thread-safe) ----
        c = self.controller
        c.on_busy_changed = _idle(self._on_busy_changed)
        c.on_rows_replaced = _idle(self._on_rows_replaced)
        c.on_row_updated = _idle(self._on_row_updated)
        c.on_total_changed = _idle(self._on_total_changed)
        c.on_progress = _idle(self.progress_label.set_text)
        c.on_log = _idle(self.win.log)
        c.on_preview = _idle(self._on_preview)
        c.on_disk_label_dirty = _idle(self.win.update_disk_label)

        self._update_total_label(0, 0)

    # ---- Observer reactions (on the Gtk main thread) ----

    def _on_busy_changed(self, busy: bool, progress_text: str) -> None:
        if busy:
            self.spinner.show()
            self.spinner.start()
            self.cancel_btn.show()
            self.scan_btn.set_sensitive(False)
            self.clean_btn.set_sensitive(False)
        else:
            self.spinner.stop()
            self.spinner.hide()
            self.cancel_btn.hide()
            self.scan_btn.set_sensitive(True)
            self._on_total_changed(
                self.controller.selected_count,
                self.controller.total_bytes,
            )
        self.progress_label.set_text(progress_text)

    def _on_rows_replaced(self, rows: list[TaskRow]) -> None:
        self.store.clear()
        for row in rows:
            self._store_append(row)

    def _on_row_updated(self, idx: int, row: TaskRow) -> None:
        if idx >= len(self.store):
            self._store_append(row)
            return
        self.store[idx][self.C_CHECK] = row.checked
        self.store[idx][self.C_NAME] = row.status_marker + row.name
        self.store[idx][self.C_SIZE_TEXT] = row.size_text
        self.store[idx][self.C_SIZE_BYTES] = row.size_bytes or 0

    def _on_total_changed(self, count: int, total_bytes: int) -> None:
        self._update_total_label(count, total_bytes)

    def _update_total_label(self, count: int, total_bytes: int) -> None:
        label = _("Selected: {size}").format(size=human(total_bytes))
        self.total_label.set_markup(f"<b>{GLib.markup_escape_text(label)}</b>")
        self.clean_btn.set_sensitive(count > 0)

    def _store_append(self, row: TaskRow) -> None:
        color, label = RISK_COLORS.get(row.risk, RISK_COLORS["medium"])
        self.store.append(
            [
                row.checked,
                row.status_marker + row.name,
                label,
                color,
                row.path,
                row.size_text,
                row.size_bytes or 0,
                row.desc,
            ]
        )

    def _on_preview(self, result: PreviewResult) -> None:
        markup = _format_preview_markup(result)
        self.preview_label.set_markup(markup)

    # ---- Widget event handlers ----

    def _on_toggle_widget(self, _r, path) -> None:
        idx = int(str(path))
        self.controller.toggle(idx)

    def _on_selection_changed(self, sel) -> None:
        model, it = sel.get_selected()
        if it is None:
            self.preview_label.set_markup(
                "<i>"
                + GLib.markup_escape_text(_("Select a row to see its contents here."))
                + "</i>"
            )
            return
        idx = model.get_path(it).get_indices()[0]
        self.controller.request_preview(idx)

    def _show_hint(self, btn) -> None:
        popover = Gtk.Popover.new(btn)
        lbl = Gtk.Label()
        lbl.set_markup(self._hint_text)
        lbl.set_line_wrap(True)
        lbl.set_max_width_chars(50)
        lbl.set_margin_start(12)
        lbl.set_margin_end(12)
        lbl.set_margin_top(12)
        lbl.set_margin_bottom(12)
        popover.add(lbl)
        popover.show_all()

    def _trigger_clean(self) -> None:
        """Confirm callback is synchronous — when the controller invokes the
        dialog, the View returns a bool here."""
        self.controller.start_clean(self._confirm_clean)

    def _confirm_clean(self, preview: CleanPreview) -> bool:
        items_str = "\n".join(f"• {name}" for _u, name in preview.items)
        remaining = preview.count - len(preview.items)
        if remaining > 0:
            items_str += "\n" + ngettext(
                "… and {n} more item",
                "… and {n} more items",
                remaining,
            ).format(n=remaining)
        header = ngettext(
            "{n} item will be deleted.",
            "{n} items will be deleted.",
            preview.count,
        ).format(n=preview.count)
        msg = (
            f"{header}\n"
            + _("Estimated gain: {size}").format(size=human(preview.total_bytes))
            + f"\n\n{items_str}"
        )
        dlg = Gtk.MessageDialog(
            transient_for=self.win,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Confirm cleanup"),
        )
        dlg.format_secondary_text(msg)
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    # ---- Backward compat (control API) ----

    @property
    def tasks(self) -> list[dict[str, Any]]:
        return self.controller.tasks

    @property
    def _busy(self) -> bool:
        return self.controller.busy


def _format_preview_markup(result: PreviewResult) -> str:
    """View-specific: build Pango markup."""
    if result.state == "scanning":
        return (
            "<i>" + GLib.markup_escape_text(_("Scanning: {path}").format(path=result.path)) + "</i>"
        )
    if result.state == "missing":
        return (
            "<i>"
            + GLib.markup_escape_text(
                _("Path missing or abstract: {path}").format(path=result.path)
            )
            + "</i>"
        )
    if result.state == "error":
        return (
            "<i>"
            + GLib.markup_escape_text(_("permission/access: {err}").format(err=result.error))
            + "</i>"
        )
    if result.state == "file":
        return (
            f"<b>📄 {GLib.markup_escape_text(_basename(result.path))}</b>  "
            f"<tt>{human(result.file_size)}</tt>"
        )
    # directory
    header_suffix = ngettext(
        "{n} item",
        "{n} items",
        result.total_items,
    ).format(n=result.total_items)
    lines = [
        f"<b>{GLib.markup_escape_text(result.path)}</b>  — {GLib.markup_escape_text(header_suffix)}"
    ]
    for item in result.items:
        icon = "📁" if item.is_dir else "📄"
        esc_name = GLib.markup_escape_text(item.name)
        suffix = ""
        if item.is_sparse:
            sparse_text = _("(sparse, nominal: {size})").format(size=human(item.nominal_size))
            suffix = f"  <span color='#888'>{GLib.markup_escape_text(sparse_text)}</span>"
        lines.append(f"  {icon} {esc_name}  <tt>{human(item.size)}</tt>{suffix}")
    remaining = result.total_items - len(result.items)
    if remaining > 0:
        more_text = ngettext(
            "… and {n} more item",
            "… and {n} more items",
            remaining,
        ).format(n=remaining)
        lines.append(f"  <i>{GLib.markup_escape_text(more_text)}</i>")
    return "\n".join(lines)


def _basename(path: str) -> str:
    import os

    return os.path.basename(path) or path


__all__ = ["TaskPanel"]
