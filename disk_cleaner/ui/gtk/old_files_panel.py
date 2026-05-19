"""OldFilesPanel — old-file scanner panel.

Calls ``make_old_files_tasks`` with a folder + age threshold (days).
Risk is high — results are the user's own files; nothing is
auto-selected.
"""

from __future__ import annotations

from ..._gtk import Gtk
from ...config import HOME
from ...i18n import _


class OldFilesPanel(Gtk.Box):
    def __init__(self, win) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_border_width(6)
        self.win = win

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(row, False, False, 0)
        row.pack_start(Gtk.Label(label=_("Folder:"), xalign=0), False, False, 0)
        self.entry = Gtk.Entry()
        downloads = HOME / "İndirilenler"
        if not downloads.exists():
            downloads = HOME / "Downloads"
        self.entry.set_text(str(downloads))
        self.entry.set_hexpand(True)
        row.pack_start(self.entry, True, True, 0)
        row.pack_start(Gtk.Label(label=_("Age (days):"), xalign=0), False, False, 0)
        self.days_spin = Gtk.SpinButton.new_with_range(1, 3650, 1)
        self.days_spin.set_value(90)
        row.pack_start(self.days_spin, False, False, 0)

        from .task_panel import TaskPanel

        self.task_panel = TaskPanel(
            win,
            tasks_provider=self._provider,
            auto_select=False,
            hint=_(
                "Files older than N days in the specified folder. "
                "High risk: these are your own files — select intentionally."
            ),
            name="oldfiles",
        )
        self.pack_start(self.task_panel, True, True, 0)

    def _provider(self, cancel=None, progress=None):
        from ..._tasks import make_old_files_tasks

        return make_old_files_tasks(
            self.entry.get_text(),
            int(self.days_spin.get_value()),
            cancel=cancel,
        )

    def set_default_path(self, path: str) -> None:
        self.entry.set_text(path)


__all__ = ["OldFilesPanel"]
