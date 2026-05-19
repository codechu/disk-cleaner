"""SuggestionPanel — the smart-suggestions View (Gtk).

The state machine is owned by
:class:`~disk_cleaner.controllers.SuggestionController`. This class is
responsible only for widget glue + filter/sort + dialogs + right-click
menu + JSON/CSV file export.
"""

from __future__ import annotations

import csv
import json
import os
import time
from collections.abc import Callable
from typing import Any

from ..._gtk import GLib, Gtk, Pango
from ...controllers import (
    GrowthInfo,
    SuggestionCleanPreview,
    SuggestionController,
    SuggestionRow,
)
from ...i18n import _, ngettext
from ...utils import human


def _idle(fn: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        GLib.idle_add(lambda: (fn(*args, **kwargs), False)[1])

    return wrapper


class SuggestionPanel(Gtk.Box):
    """View for the controller that runs all scanners in the background."""

    # TreeStore column indices
    (
        C_CHECK,
        C_NAME,
        C_SCORE_TXT,
        C_SCORE,
        C_SIZE_TXT,
        C_SIZE,
        C_REASON,
        C_RISK_COLOR,
        C_KIND,
        C_IS_GROUP,
        C_TASK_ID,
    ) = range(11)

    def __init__(
        self,
        win,
        controller: SuggestionController | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_border_width(6)
        self.win = win
        self.controller: SuggestionController = controller or SuggestionController()

        # ---- Top bar ----
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(bar, False, False, 0)
        self.scan_btn = Gtk.Button(label=_("🎯  Smart scan"))
        self.scan_btn.get_style_context().add_class("suggested-action")
        self.scan_btn.connect("clicked", lambda *_: self.controller.start_scan())
        bar.pack_start(self.scan_btn, False, False, 0)

        self.cancel_btn = Gtk.Button(label="⛔")
        self.cancel_btn.connect("clicked", lambda *_: self.controller.cancel())
        self.cancel_btn.set_no_show_all(True)
        bar.pack_start(self.cancel_btn, False, False, 0)

        self.spinner = Gtk.Spinner()
        self.spinner.set_no_show_all(True)
        bar.pack_start(self.spinner, False, False, 0)

        self.progress_label = Gtk.Label(xalign=0)
        self.progress_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        bar.pack_start(self.progress_label, True, True, 0)

        # Risk filtresi (View-side, refilter)
        self.risk_filter = Gtk.ComboBoxText()
        self.risk_filter.append("low", _("Safe only"))
        self.risk_filter.append("medium", _("Including medium"))
        self.risk_filter.append("all", _("All (including active)"))
        self.risk_filter.set_active_id("medium")
        self.risk_filter.connect("changed", lambda *_: self.filter.refilter())
        bar.pack_end(self.risk_filter, False, False, 0)
        bar.pack_end(Gtk.Label(label=_("Show:"), xalign=1), False, False, 0)

        # ---- Store + filter + sort ----
        self.store = Gtk.TreeStore(
            bool,
            str,
            str,
            int,
            str,
            "guint64",
            str,
            str,
            str,
            bool,
            int,
        )
        self.filter = self.store.filter_new()
        self.filter.set_visible_func(self._row_visible)
        self.sort = Gtk.TreeModelSort(model=self.filter)
        self.sort.set_sort_column_id(self.C_SCORE, Gtk.SortType.DESCENDING)

        # Map: (group_idx, child_idx) → Gtk.TreeIter (controller → View)
        self._iter_map: dict[tuple[int, int], Gtk.TreeIter] = {}

        # ---- Empty / results stack ----
        self.content_stack = Gtk.Stack()
        self.content_stack.set_vexpand(True)
        self.pack_start(self.content_stack, True, True, 0)

        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.set_halign(Gtk.Align.CENTER)
        icon_lbl = Gtk.Label()
        icon_lbl.set_markup("<span size='65000'>🎯</span>")
        empty_box.pack_start(icon_lbl, False, False, 0)
        title_lbl = Gtk.Label()
        title_lbl.set_markup(
            "<span size='larger' weight='bold'>"
            + GLib.markup_escape_text(_("No scan yet"))
            + "</span>"
        )
        empty_box.pack_start(title_lbl, False, False, 0)
        sub_lbl = Gtk.Label()
        sub_lbl.set_markup(
            _(
                "<span foreground='#888'>Press the <b>🎯 Smart scan</b> button "
                "above to view suggestions.\n"
                "System caches, old projects and large files are scored "
                "automatically.</span>"
            )
        )
        sub_lbl.set_justify(Gtk.Justification.CENTER)
        empty_box.pack_start(sub_lbl, False, False, 0)
        self.content_stack.add_named(empty_box, "empty")

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self.content_stack.add_named(scroll, "results")
        self.tree = Gtk.TreeView(model=self.sort)
        self.tree.connect("button-press-event", self._on_button_press)

        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self._on_toggle_widget)
        self.tree.append_column(Gtk.TreeViewColumn("✓", toggle, active=self.C_CHECK))

        col_name = Gtk.TreeViewColumn(_("Item"), Gtk.CellRendererText(), text=self.C_NAME)
        col_name.set_min_width(320)
        col_name.set_resizable(True)
        self.tree.append_column(col_name)

        size_r = Gtk.CellRendererText()
        size_r.set_property("xalign", 1.0)
        col_size = Gtk.TreeViewColumn(_("Size"), size_r, text=self.C_SIZE_TXT)
        col_size.set_sort_column_id(self.C_SIZE)
        col_size.set_min_width(90)
        self.tree.append_column(col_size)

        score_r = Gtk.CellRendererText()
        score_r.set_property("xalign", 1.0)
        col_score = Gtk.TreeViewColumn(
            _("Score"),
            score_r,
            text=self.C_SCORE_TXT,
            foreground=self.C_RISK_COLOR,
        )
        col_score.set_sort_column_id(self.C_SCORE)
        col_score.set_min_width(60)
        self.tree.append_column(col_score)

        col_reason = Gtk.TreeViewColumn(
            _("Reason"),
            Gtk.CellRendererText(),
            text=self.C_REASON,
        )
        col_reason.set_min_width(280)
        self.tree.append_column(col_reason)

        scroll.add(self.tree)

        # ---- Action bar ----
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(action_bar, False, False, 0)
        self.total_label = Gtk.Label(xalign=0)
        action_bar.pack_start(self.total_label, True, True, 0)

        target_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        target_box.pack_start(Gtk.Label(label=_("Target:"), xalign=1), False, False, 0)
        self.target_spin = Gtk.SpinButton.new_with_range(1, 1000, 1)
        self.target_spin.set_value(10)
        self.target_spin.set_width_chars(4)
        target_box.pack_start(self.target_spin, False, False, 0)
        target_box.pack_start(Gtk.Label(label=_("GB"), xalign=0), False, False, 0)
        pick_btn = Gtk.Button(label=_("Pick"))
        pick_btn.set_tooltip_text(
            _(
                "Selects low-risk, highest-scored items until the total target "
                "is reached (previous selection is reset)."
            )
        )
        pick_btn.connect("clicked", lambda *_: self._on_pick_target())
        target_box.pack_start(pick_btn, False, False, 0)
        action_bar.pack_start(target_box, False, False, 0)

        self.all_btn = Gtk.Button(label=_("All"))
        self.all_btn.connect("clicked", lambda *_: self.controller.select_all())
        action_bar.pack_start(self.all_btn, False, False, 0)
        self.none_btn = Gtk.Button(label=_("None"))
        self.none_btn.connect("clicked", lambda *_: self.controller.select_none())
        action_bar.pack_start(self.none_btn, False, False, 0)

        self.clean_btn = Gtk.Button(label=_("🧹  Clean selected"))
        self.clean_btn.get_style_context().add_class("suggested-action")
        self.clean_btn.connect("clicked", lambda *_: self._trigger_clean())
        self.clean_btn.set_sensitive(False)
        action_bar.pack_start(self.clean_btn, False, False, 0)

        self.export_btn = Gtk.Button(label=_("📤  Export"))
        self.export_btn.set_tooltip_text(_("Save scan results as JSON or CSV."))
        self.export_btn.connect("clicked", self.on_export)
        action_bar.pack_start(self.export_btn, False, False, 0)

        self._update_total_label(0, 0)

        # ---- Controller observer wiring ----
        c = self.controller
        c.on_busy_changed = _idle(self._on_busy_changed)
        c.on_rows_replaced = _idle(self._on_rows_replaced)
        c.on_row_updated = _idle(self._on_row_updated)
        c.on_total_changed = _idle(self._on_total_changed)
        c.on_row_removed = _idle(self._on_row_removed)
        c.on_progress = _idle(self.progress_label.set_text)
        c.on_log = _idle(self.win.log)
        c.on_disk_label_dirty = _idle(self.win.update_disk_label)

    # ---- Filter ----

    def _row_visible(self, model, it, _data) -> bool:
        mode = self.risk_filter.get_active_id()
        if mode == "all":
            return True
        color = model[it][self.C_RISK_COLOR]
        if mode == "low":
            return color == "#1a7f37"
        if mode == "medium":
            return color != "#cf222e"
        return True

    # ---- Observer reactions (Gtk main thread) ----

    def _on_busy_changed(self, busy: bool, progress: str) -> None:
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
            self._on_total_changed(self.controller.selected_count, self.controller.total_bytes)
        self.progress_label.set_text(progress)

    def _on_rows_replaced(
        self,
        rows: list[SuggestionRow],
        growth: GrowthInfo | None,
    ) -> None:
        if growth and growth.items:
            self._log_growth(growth)
        self.store.clear()
        self._iter_map.clear()
        for gi, row in enumerate(rows):
            if row.is_group:
                group_iter = self.store.append(None, _row_to_columns(row))
                self._iter_map[(gi, -1)] = group_iter
                for ci, child in enumerate(row.children):
                    child_iter = self.store.append(group_iter, _row_to_columns(child))
                    self._iter_map[(gi, ci)] = child_iter
            else:
                row_iter = self.store.append(None, _row_to_columns(row))
                self._iter_map[(gi, -1)] = row_iter
        self.tree.expand_all()
        total = self.controller.total_items
        self.content_stack.set_visible_child_name("results" if total > 0 else "empty")

    def _on_row_updated(
        self,
        gi: int,
        ci: int,
        row: SuggestionRow,
    ) -> None:
        key = (gi, -1) if ci < 0 else (gi, ci)
        it = self._iter_map.get(key)
        if it is None:
            return
        cols = _row_to_columns(row)
        for col_idx, val in enumerate(cols):
            self.store.set_value(it, col_idx, val)

    def _on_row_removed(self, gi: int, ci: int) -> None:
        key = (gi, -1) if ci < 0 else (gi, ci)
        it = self._iter_map.pop(key, None)
        if it is None:
            return
        try:
            self.store.remove(it)
        except Exception:
            pass

    def _on_total_changed(self, count: int, total_bytes: int) -> None:
        self._update_total_label(count, total_bytes)

    def _update_total_label(self, count: int, total_bytes: int) -> None:
        label = ngettext(
            "{n} item selected — {size}",
            "{n} items selected — {size}",
            count,
        ).format(n=count, size=human(total_bytes))
        self.total_label.set_markup(f"<b>{GLib.markup_escape_text(label)}</b>")
        self.clean_btn.set_sensitive(count > 0)

    def _log_growth(self, growth: GrowthInfo) -> None:
        ago = (time.time() - growth.prev_scanned_at) / 86400
        lines = [_("\n📈 Largest growth over the last ~{days}d:").format(days=int(ago))]
        for g in growth.items[:5]:
            if g.prev_size == 0:
                lines.append(
                    _("  + {path} → {size} (new)").format(path=g.path, size=human(g.current_size))
                )
            else:
                pct = g.delta / g.prev_size * 100
                lines.append(
                    _("  + {path} → {size} (grew by {delta}, {pct:.0f}%)").format(
                        path=g.path,
                        size=human(g.current_size),
                        delta=human(g.delta),
                        pct=pct,
                    )
                )
        self.win.log("\n".join(lines) + "\n")

    # ---- Widget event handlers ----

    def _on_toggle_widget(self, _r, path) -> None:
        sort_iter = self.sort.get_iter(path)
        filter_iter = self.sort.convert_iter_to_child_iter(sort_iter)
        store_iter = self.filter.convert_iter_to_child_iter(filter_iter)
        gi, ci = self._indices_for(store_iter)
        if gi is None:
            return
        self.controller.toggle(gi, ci)

    def _indices_for(self, store_iter) -> tuple[int | None, int | None]:
        store_path = self.store.get_path(store_iter)
        indices = store_path.get_indices()
        if len(indices) == 1:
            return indices[0], None
        if len(indices) == 2:
            return indices[0], indices[1]
        return None, None

    def _on_pick_target(self) -> None:
        target_bytes = int(self.target_spin.get_value()) * (1024**3)
        self.controller.select_target(target_bytes)

    def _trigger_clean(self) -> None:
        self.controller.start_clean(self._confirm_clean)

    def _confirm_clean(self, preview: SuggestionCleanPreview) -> bool:
        items_str = "\n".join(f"• {name}" for _u1, _u2, name in preview.items)
        remaining = preview.count - len(preview.items)
        if remaining > 0:
            items_str += "\n" + ngettext(
                "… and {n} more item",
                "… and {n} more items",
                remaining,
            ).format(n=remaining)
        dlg = Gtk.MessageDialog(
            transient_for=self.win,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Confirm smart cleanup"),
        )
        header = ngettext(
            "{n} item · estimated gain: {size}",
            "{n} items · estimated gain: {size}",
            preview.count,
        ).format(n=preview.count, size=human(preview.total_bytes))
        dlg.format_secondary_text(f"{header}\n\n{items_str}")
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    def _on_button_press(self, _w, event) -> bool:
        if event.button != 3:
            return False
        path_info = self.tree.get_path_at_pos(int(event.x), int(event.y))
        if not path_info:
            return False
        sort_path = path_info[0]
        sort_iter = self.sort.get_iter(sort_path)
        filter_iter = self.sort.convert_iter_to_child_iter(sort_iter)
        store_iter = self.filter.convert_iter_to_child_iter(filter_iter)
        if store_iter is None:
            return False
        gi, ci = self._indices_for(store_iter)
        if gi is None:
            return False
        # Leaves only
        if ci is None:
            row = self.controller.rows[gi]
            if row.is_group:
                return False
        tid = self.store[store_iter][self.C_TASK_ID]
        task = self.controller.tasks.get(tid)
        if not task:
            return False
        path = task.get("path", "")
        menu = Gtk.Menu()
        item = Gtk.MenuItem(label=_("🚫  Don't suggest this path again"))
        item.connect(
            "activate",
            lambda *_: self.controller.blacklist_and_remove(gi, ci),
        )
        menu.append(item)
        info = Gtk.MenuItem(label=_("path: {path}").format(path=path[:60]))
        info.set_sensitive(False)
        menu.append(info)
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    # ---- Export ----

    def on_export(self, _b) -> None:
        rows = self.controller.export_rows()
        if not rows:
            return
        dlg = Gtk.FileChooserDialog(
            title=_("Save scan result"),
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
        dlg.set_current_name(f"disk_cleaner_scan_{ts}.json")
        for ext, name in (("json", "JSON"), ("csv", "CSV")):
            ff = Gtk.FileFilter()
            ff.set_name(f"{name} (*.{ext})")
            ff.add_pattern(f"*.{ext}")
            dlg.add_filter(ff)
        resp = dlg.run()
        target = dlg.get_filename() if resp == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if not target:
            return
        try:
            if target.lower().endswith(".csv"):
                _write_csv(target, rows)
            else:
                if not target.lower().endswith(".json"):
                    target += ".json"
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "host": os.uname().nodename,
                            "items": [_export_dict(r) for r in rows],
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )
            self.win.log(
                _("✓ {n} rows saved: {target}\n").format(
                    n=len(rows),
                    target=target,
                )
            )
        except Exception as e:
            self.win.log(_("✗ Export error: {err}\n").format(err=e))

    # ---- Backward compat ----

    @property
    def tasks(self) -> dict[int, dict[str, Any]]:
        return self.controller.tasks

    @property
    def _busy(self) -> bool:
        return self.controller.busy


# ---- helpers ----


def _row_to_columns(row: SuggestionRow) -> list[Any]:
    """SuggestionRow → Gtk.TreeStore row columns."""
    return [
        row.checked,
        row.status_marker + row.name,
        f"{row.score}",
        row.score,
        row.size_text,
        row.size_bytes,
        row.reason,
        row.risk_color,
        row.kind,
        row.is_group,
        row.tid,
    ]


def _export_dict(r) -> dict:
    return {
        "name": r.name,
        "path": r.path,
        "kind": r.kind,
        "size_bytes": r.size_bytes,
        "size_human": r.size_human,
        "score": r.score,
        "reason": r.reason,
        "risk": r.risk,
        "selected": r.selected,
    }


def _write_csv(target: str, rows) -> None:
    with open(target, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "name",
                "path",
                "kind",
                "size_bytes",
                "size_human",
                "score",
                "reason",
                "risk",
                "selected",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(_export_dict(r))


__all__ = ["SuggestionPanel"]
