"""MainWindow — the application's top-level window shell (Gtk View).

The state machine is owned by
:class:`~disk_cleaner.controllers.MainController`. This class is only
responsible for:

- Header bar, mount combo, trash/dry-run checkboxes, watchdog button
- BTRFS/ZFS InfoBar, disk usage label
- Panel organization via Notebook + Stack
- Log expander widget
- Tray icon and ControlServer startup

Mount listing, disk-usage parsing, watchdog start/stop, and settings
persistence all live on the controller.
"""

from __future__ import annotations

import os

import gi

from ..._gtk import Gdk, GLib, Gtk
from ...api.server import ControlServer
from ...config import HOME
from ...controllers import (
    DiskUsage,
    MainController,
    SuggestionController,
    TreemapController,
)
from ...i18n import _
from ...settings import SETTINGS
from .dynamic_panel import DynamicPanel
from .old_files_panel import OldFilesPanel
from .suggestion_panel import SuggestionPanel
from .task_panel import TaskPanel
from .treemap_panel import TreemapPanel


def try_init_tray(on_open, on_quit):
    """Create and return a tray icon if AppIndicator3 / Ayatana is available."""
    indicator = None
    for ver_pkg in (("AyatanaAppIndicator3", "0.1"), ("AppIndicator3", "0.1")):
        try:
            gi.require_version(*ver_pkg)
            mod = __import__("gi.repository", fromlist=[ver_pkg[0]])
            Ai = getattr(mod, ver_pkg[0])
            indicator = Ai.Indicator.new(
                "disk-cleaner",
                "drive-harddisk-symbolic",
                Ai.IndicatorCategory.APPLICATION_STATUS,
            )
            indicator.set_status(Ai.IndicatorStatus.ACTIVE)
            menu = Gtk.Menu()
            m_open = Gtk.MenuItem(label=_("Open window"))
            m_open.connect("activate", lambda *_: on_open())
            menu.append(m_open)
            menu.append(Gtk.SeparatorMenuItem())
            m_q = Gtk.MenuItem(label=_("Quit"))
            m_q.connect("activate", lambda *_: on_quit())
            menu.append(m_q)
            menu.show_all()
            indicator.set_menu(menu)
            return indicator
        except Exception:
            continue
    return None


def _idle(fn):
    def wrapper(*args, **kwargs):
        GLib.idle_add(lambda: (fn(*args, **kwargs), False)[1])

    return wrapper


class MainWindow(Gtk.Window):
    def __init__(
        self,
        controller: MainController | None = None,
    ) -> None:
        super().__init__(title=_("Disk Cleaner"))
        self.set_default_size(900, 620)
        self.set_resizable(True)
        geom = Gdk.Geometry()
        geom.min_width = 600
        geom.min_height = 400
        self.set_geometry_hints(None, geom, Gdk.WindowHints.MIN_SIZE)
        self.set_border_width(8)

        self.controller: MainController = controller or MainController()

        headerbar = Gtk.HeaderBar()
        headerbar.set_show_close_button(True)
        headerbar.set_title(_("Disk Cleaner"))
        headerbar.set_decoration_layout("menu:minimize,maximize,close")
        self.set_titlebar(headerbar)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(outer)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.pack_start(header, False, False, 0)

        # ---- Mount combo ----
        self.mount_combo = Gtk.ComboBoxText()
        for m in self.controller.mounts:
            self.mount_combo.append(
                m.target,
                _("{target}  ({avail} free)").format(target=m.target, avail=m.avail),
            )
        self.mount_combo.set_active_id(self.controller.current_mount)
        self.mount_combo.connect(
            "changed",
            lambda c: self.controller.set_mount(c.get_active_id() or "/"),
        )
        header.pack_start(self.mount_combo, False, False, 0)

        self.disk_label = Gtk.Label(xalign=0)
        self.disk_label.set_use_markup(True)
        header.pack_start(self.disk_label, True, True, 0)

        # ---- Trash / Dry / Watchdog ----
        from ... import runtime

        self.trash_chk = Gtk.CheckButton(label=_("🗑 Trash"))
        self.trash_chk.set_active(runtime.TRASH_MODE)
        self.trash_chk.set_tooltip_text(
            _(
                "On: items go to trash (reversible).\n"
                "Off: permanent deletion.\n"
                "Subprocess commands (npm, docker, apt) are always permanent."
            )
        )
        self.trash_chk.connect(
            "toggled",
            lambda c: self.controller.set_trash_mode(c.get_active()),
        )
        header.pack_end(self.trash_chk, False, False, 0)

        self.dry_chk = Gtk.CheckButton(label=_("🧪 Dry-run"))
        self.dry_chk.set_active(runtime.DRY_RUN)
        self.dry_chk.set_tooltip_text(
            _(
                "On: nothing is deleted, only logs what would happen.\n"
                "For testing and risk analysis."
            )
        )
        self.dry_chk.connect(
            "toggled",
            lambda c: self.controller.set_dry_run(c.get_active()),
        )
        header.pack_end(self.dry_chk, False, False, 0)

        self.watchdog_btn = Gtk.Button()
        self._refresh_watchdog_btn(self.controller.watchdog_status())
        self.watchdog_btn.set_tooltip_text(
            _(
                "Monitor disk usage in the background.\n"
                "Threshold: {threshold}% — interval {interval}s"
            ).format(
                threshold=SETTINGS.get("watchdog_threshold", 85),
                interval=SETTINGS.get("watchdog_interval", 600),
            )
        )
        self.watchdog_btn.connect("clicked", lambda *_: self.controller.toggle_watchdog())
        header.pack_end(self.watchdog_btn, False, False, 0)

        # ---- Theme selector (settings-stored, takes effect on restart) ----
        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.append("auto", _("Auto"))
        self.theme_combo.append("light", _("Light"))
        self.theme_combo.append("dark", _("Dark"))
        self.theme_combo.set_active_id(SETTINGS.get("theme", "auto"))
        self.theme_combo.set_tooltip_text(
            _("Color theme.\nAuto = follow system. Change takes effect after restart.")
        )
        self.theme_combo.connect("changed", self._on_theme_changed)
        header.pack_end(self.theme_combo, False, False, 0)

        # ---- Language selector (settings-stored, takes effect on restart) ----
        self.lang_combo = Gtk.ComboBoxText()
        self.lang_combo.append("en", "English")
        self.lang_combo.append("tr", "Türkçe")
        current_lang = SETTINGS.get("language", "")
        self.lang_combo.set_active_id(current_lang or "en")
        self.lang_combo.set_tooltip_text(_("Display language.\nChange takes effect after restart."))
        self.lang_combo.connect("changed", self._on_lang_changed)
        header.pack_end(self.lang_combo, False, False, 0)

        # ---- BTRFS/ZFS InfoBar ----
        self.fs_warning = Gtk.InfoBar()
        self.fs_warning.set_message_type(Gtk.MessageType.WARNING)
        self.fs_warning.set_no_show_all(True)
        warn_lbl = Gtk.Label(xalign=0)
        warn_lbl.set_line_wrap(True)
        self.fs_warning_label = warn_lbl
        self.fs_warning.get_content_area().add(warn_lbl)
        outer.pack_start(self.fs_warning, False, False, 0)

        # ---- Notebook ----
        notebook = Gtk.Notebook()
        outer.pack_start(notebook, True, True, 0)

        # Tab 0: Smart suggestions
        self.suggestion_panel = SuggestionPanel(self, controller=SuggestionController())
        notebook.append_page(self.suggestion_panel, Gtk.Label(label=_("🎯  Suggestions")))

        # Tab 1: Cleanup
        from ... import _tasks

        sys_panel = TaskPanel(
            self,
            tasks_provider=lambda: _tasks.SYSTEM_TASKS,
            auto_select=True,
            hint=_(
                "System caches, package caches, old snaps. "
                "Low-risk + >100MB items are auto-selected."
            ),
            name="system",
        )
        proj_panel = DynamicPanel(
            self,
            build_tasks_from_input=_tasks.make_artifact_tasks,
            default_input=str(HOME / "workspace"),
            input_label=_("Workspace:"),
            hint=_(
                "node_modules, target, build, dist, .next, .gradle, venv, "
                "__pycache__ etc. Projects modified in the last 14 days get a "
                "red ACTIVE label and are not auto-selected."
            ),
            name="artifacts",
        )
        explorer = DynamicPanel(
            self,
            build_tasks_from_input=_tasks.make_folder_explorer_tasks,
            default_input=str(HOME / ".opencode"),
            input_label=_("Folder:"),
            hint=_("Lists direct children of a folder with their sizes."),
            name="explorer",
        )
        old_panel = OldFilesPanel(self)
        dup_panel = DynamicPanel(
            self,
            build_tasks_from_input=_tasks.make_duplicate_tasks,
            default_input=str(
                HOME / "İndirilenler" if (HOME / "İndirilenler").exists() else HOME / "Downloads"
            ),
            input_label=_("Folder:"),
            hint=_(
                "Finds files with identical content (≥1MB). The newest in "
                "each group is kept; extras are listed."
            ),
            name="duplicates",
        )
        empty_panel = DynamicPanel(
            self,
            build_tasks_from_input=_tasks.make_empty_tasks,
            default_input=str(HOME / "workspace"),
            input_label=_("Folder:"),
            hint=_("Empty folders and 0-byte files — skeletal leftovers from projects."),
            name="empty",
        )
        sim_panel = DynamicPanel(
            self,
            build_tasks_from_input=_tasks.make_similar_image_tasks,
            default_input=str(
                HOME / "Resimler" if (HOME / "Resimler").exists() else HOME / "Pictures"
            ),
            input_label=_("Folder:"),
            hint=_(
                "Finds visually similar photos (dHash + Hamming). Different "
                "shots of the same scene, compressed copies — the largest is "
                "kept. Requires Pillow."
            ),
            name="similar",
        )
        apps_panel = DynamicPanel(
            self,
            build_tasks_from_input=_tasks.make_app_uninstall_tasks,
            default_input=_("dpkg packages"),
            input_label=_("(automatic)"),
            hint=_(
                "Lists installed applications (≥5MB) by size. The selected "
                "package is removed with apt purge + ~/.config/<x>, "
                "~/.cache/<x>, ~/.local/share/<x> shared folders are also "
                "deleted. HIGH RISK — select intentionally."
            ),
            name="apps",
        )

        self.sys_panel = sys_panel
        self.dynamic_panels = [
            proj_panel,
            explorer,
            old_panel,
            dup_panel,
            empty_panel,
            sim_panel,
            apps_panel,
        ]
        self._panels_by_key = {
            "artifacts": proj_panel,
            "explorer": explorer,
            "oldfiles": old_panel,
            "duplicates": dup_panel,
            "empty": empty_panel,
            "similar": sim_panel,
            "apps": apps_panel,
        }
        saved_entries = SETTINGS.get("entries", {})
        for key, panel in self._panels_by_key.items():
            if key in saved_entries:
                panel.entry.set_text(saved_entries[key])
        for panel in self._panels_by_key.values():
            panel.entry.connect("changed", lambda *_: GLib.idle_add(self._save_settings))

        cleanup_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cleanup_box.set_border_width(6)
        selector_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        selector_row.pack_start(Gtk.Label(label=_("Scan type:"), xalign=0), False, False, 0)
        self.cleanup_combo = Gtk.ComboBoxText()
        self.cleanup_combo.append("sys", _("System cache & packages"))
        self.cleanup_combo.append("proj", _("Project artifacts (node_modules, build…)"))
        self.cleanup_combo.append("explorer", _("Folder explorer (look inside)"))
        self.cleanup_combo.append("old", _("Old files"))
        self.cleanup_combo.append("dup", _("Duplicates"))
        self.cleanup_combo.append("empty", _("Empty folders + 0-byte files"))
        self.cleanup_combo.append("similar", _("Similar images (perceptual hash)"))
        self.cleanup_combo.append("apps", _("App uninstaller (apt + cache)"))
        self.cleanup_combo.set_active(0)
        self.cleanup_combo.connect("changed", self._on_cleanup_changed)
        selector_row.pack_start(self.cleanup_combo, True, True, 0)
        cleanup_box.pack_start(selector_row, False, False, 0)

        self.cleanup_stack = Gtk.Stack()
        self.cleanup_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.cleanup_stack.set_transition_duration(150)
        self.cleanup_stack.add_named(sys_panel, "sys")
        self.cleanup_stack.add_named(proj_panel, "proj")
        self.cleanup_stack.add_named(explorer, "explorer")
        self.cleanup_stack.add_named(old_panel, "old")
        self.cleanup_stack.add_named(dup_panel, "dup")
        self.cleanup_stack.add_named(empty_panel, "empty")
        self.cleanup_stack.add_named(sim_panel, "similar")
        self.cleanup_stack.add_named(apps_panel, "apps")
        cleanup_box.pack_start(self.cleanup_stack, True, True, 0)
        notebook.append_page(cleanup_box, Gtk.Label(label=_("🧹  Cleanup")))

        # Tab 2: Disk map
        treemap_panel = TreemapPanel(self, controller=TreemapController())
        notebook.append_page(treemap_panel, Gtk.Label(label=_("📊  Disk map")))
        self.treemap_panel = treemap_panel
        self._panels_by_key["treemap"] = treemap_panel
        treemap_panel.entry.connect("changed", lambda *_: GLib.idle_add(self._save_settings))

        # ---- Log expander ----
        log_exp = Gtk.Expander(label=_("📜  Log"))
        log_exp.set_expanded(False)
        outer.pack_start(log_exp, False, False, 0)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_size_request(-1, 160)
        log_exp.add(log_scroll)
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_buf = self.log_view.get_buffer()
        log_scroll.add(self.log_view)

        # ---- Controller observers ----
        c = self.controller
        c.on_mount_changed = _idle(self._on_mount_changed)
        c.on_disk_usage_updated = _idle(self._on_disk_usage_updated)
        c.on_trash_mode_changed = _idle(lambda val: self.trash_chk.set_active(val))
        c.on_dry_run_changed = _idle(lambda val: self.dry_chk.set_active(val))
        c.on_watchdog_status_changed = _idle(self._refresh_watchdog_btn)
        c.on_log = _idle(self.log)
        c.on_fs_warning_changed = _idle(self._on_fs_warning_changed)

        # Initial state
        self.controller.refresh_disk_usage()
        self._on_fs_warning_changed(self.controller.fs_warning_for(self.controller.current_mount))
        self.log(_("Ready. Trash mode ON — deleted items can be restored.\n"))

        # Control API
        if not os.environ.get("DC_NO_CONTROL"):
            try:
                self.control_server = ControlServer(self)
                self.control_server.start()
            except Exception as e:
                self.log(_("Could not start control server: {err}\n").format(err=e))

        # Tray icon
        self.tray = try_init_tray(
            on_open=lambda: (self.present(), self.deiconify()),
            on_quit=lambda: Gtk.main_quit(),
        )
        if self.tray:
            self.log(_("Tray icon created.\n"))

    # ---- Observer reactions ----

    def _on_mount_changed(self, target: str) -> None:
        # Mount changed — let panels update their default paths
        for p in self.dynamic_panels:
            p.set_default_path(target)
        if hasattr(self, "treemap_panel"):
            self.treemap_panel.set_default_path(target)
        # Keep the combo in sync (already correct if triggered from controller's set_mount)
        if self.mount_combo.get_active_id() != target:
            self.mount_combo.set_active_id(target)

    def _on_disk_usage_updated(self, usage: DiskUsage | None) -> None:
        if usage is None:
            self.disk_label.set_markup("")
            return
        self.disk_label.set_markup(usage.label_markup)

    def _refresh_watchdog_btn(self, running: bool) -> None:
        if running:
            self.watchdog_btn.set_label(_("👁 Watching"))
            self.watchdog_btn.get_style_context().add_class("suggested-action")
        else:
            self.watchdog_btn.set_label(_("👁 Watching: Off"))
            self.watchdog_btn.get_style_context().remove_class("suggested-action")

    def _on_fs_warning_changed(self, msg: str | None) -> None:
        if msg:
            self.fs_warning_label.set_markup(_fs_warning_markup(msg))
            self.fs_warning.show()
        else:
            self.fs_warning.hide()

    # ---- Widget event handlers ----

    def _on_cleanup_changed(self, combo) -> None:
        self.cleanup_stack.set_visible_child_name(combo.get_active_id())

    def _on_lang_changed(self, combo) -> None:
        new_lang = combo.get_active_id() or "en"
        old_lang = SETTINGS.get("language", "")
        if old_lang == new_lang:
            return
        SETTINGS["language"] = new_lang
        from ... import events
        from ...settings import save_settings

        save_settings(SETTINGS)
        # User-initiated preference change → publish on its own channel
        events.emit(
            "prefs.language.changed",
            source="user",
            channel="prefs",
            old=old_lang or None,
            new=new_lang,
        )
        self.log(_("Language set to {lang}. Restart to apply.\n").format(lang=new_lang))

    def _on_theme_changed(self, combo) -> None:
        new_theme = combo.get_active_id() or "auto"
        old_theme = SETTINGS.get("theme", "auto")
        if old_theme == new_theme:
            return
        SETTINGS["theme"] = new_theme
        from ... import events
        from ...settings import save_settings

        save_settings(SETTINGS)
        events.emit(
            "prefs.theme.changed", source="user", channel="prefs", old=old_theme, new=new_theme
        )
        self.log(_("Theme set to {theme}. Restart to apply.\n").format(theme=new_theme))

    def _save_settings(self) -> None:
        entries = {key: p.entry.get_text() for key, p in self._panels_by_key.items()}
        self.controller.save_panel_entries(entries)

    # ---- Public helpers ----

    def log(self, text: str) -> None:
        end = self.log_buf.get_end_iter()
        self.log_buf.insert(end, text)
        mark = self.log_buf.create_mark(None, self.log_buf.get_end_iter(), False)
        self.log_view.scroll_to_mark(mark, 0, False, 0, 0)

    def update_disk_label(self) -> None:
        """Backward compat — delegate to the controller."""
        self.controller.refresh_disk_usage()

    # ---- Backward compat (control API) ----

    @property
    def mounts(self) -> list[dict]:
        return [
            {
                "target": m.target,
                "source": m.source,
                "fstype": m.fstype,
                "size": m.size,
                "used": m.used,
                "avail": m.avail,
                "pcent": m.pcent,
            }
            for m in self.controller.mounts
        ]


def _fs_warning_markup(plain: str) -> str:
    """Convert plain text from ``MainController.fs_warning_for`` to Pango markup."""
    # Plain: "⚠  BTRFS filesystem — ... to inspect: btdu"
    if "—" in plain:
        head, tail = plain.split("—", 1)
        # Wrap the FS name in <b>...</b>
        for fs in ("BTRFS", "ZFS"):
            if fs in head:
                head = head.replace(fs, f"<b>{fs}</b>")
        # Wrap the tool name in <tt>...</tt>
        if ":" in tail:
            tail_lead, tool = tail.rsplit(":", 1)
            tail = f"{tail_lead}: <tt>{tool.strip()}</tt>"
        return head + "—" + tail
    return plain


__all__ = ["MainWindow", "try_init_tray"]
