# SPDX-License-Identifier: GPL-3.0-or-later

"""DynamicPanel — builds Tasks from user input, wraps a ``TaskPanel``.

Used in the Duplicate / Empty / Similar / Explorer tabs: a "Folder"
entry on top, a :class:`TaskPanel` below. When the entry changes, the
provider callback is invoked with the fresh input.
"""

from __future__ import annotations

from ..._gtk import Gtk


class DynamicPanel(Gtk.Box):
    """Input field on top, TaskPanel below."""

    def __init__(
        self,
        win,
        build_tasks_from_input,
        default_input: str,
        input_label: str,
        hint: str,
        name: str = "dynamic",
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_border_width(6)
        self.win = win
        self.build_tasks_from_input = build_tasks_from_input

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(row, False, False, 0)
        row.pack_start(Gtk.Label(label=input_label, xalign=0), False, False, 0)
        self.entry = Gtk.Entry()
        self.entry.set_text(default_input)
        self.entry.set_hexpand(True)
        row.pack_start(self.entry, True, True, 0)

        from .task_panel import TaskPanel

        self.name = name
        self.task_panel = TaskPanel(
            win,
            tasks_provider=self._provider,
            auto_select=False,
            hint=hint,
            name=name,
        )
        self.pack_start(self.task_panel, True, True, 0)

    def _provider(self, cancel=None, progress=None):
        try:
            return self.build_tasks_from_input(
                self.entry.get_text(), cancel=cancel, progress=progress
            )
        except TypeError:
            return self.build_tasks_from_input(self.entry.get_text(), cancel=cancel)

    def set_default_path(self, path: str) -> None:
        """Called when the mount changes — updates the entry."""
        self.entry.set_text(path)


__all__ = ["DynamicPanel"]
