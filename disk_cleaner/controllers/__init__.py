# SPDX-License-Identifier: GPL-3.0-or-later

"""Presenter / Controller layer — view-independent UI state machines.

Design contract:

1. **No GTK/Qt/HTML imports.** Only domain modules (``viz``, ``core``,
   ``_tasks``, ``settings``, ``events``, ``runtime``, ``utils``) plus
   ``threading``/``time`` are used.
2. **Observer pattern**: each controller has ``on_*`` callable
   attributes; the View registers them.
3. **Thread-safety**: callbacks may be invoked from worker threads;
   the View is responsible for marshalling onto its own UI thread
   (``GLib.idle_add`` wrapper for Gtk).
4. **Animation/hover/widget state stays in the View** — controllers
   are pure data state machines.
5. **Headless test**: ``pytest`` runs controllers without a GUI.

Current controllers:

- :class:`~disk_cleaner.controllers.main.MainController` — top window
  shell (mount, trash/dry, watchdog, disk usage)
- :class:`~disk_cleaner.controllers.treemap.TreemapController` — disk map
- :class:`~disk_cleaner.controllers.task_list.TaskListController` —
  scan/select/clean flow (the backing for TaskPanel)
- :class:`~disk_cleaner.controllers.suggestion.SuggestionController` —
  smart scan + score + group + auto-select (the backing for
  SuggestionPanel)
"""

from __future__ import annotations

from .main import DiskUsage, MainController, Mount, read_disk_usage
from .suggestion import CleanPreview as SuggestionCleanPreview
from .suggestion import (
    ExportRow,
    GrowthInfo,
    GrowthItem,
    SuggestionController,
    SuggestionRow,
)
from .task_list import (
    CleanPreview,
    PreviewItem,
    PreviewResult,
    TaskListController,
    TaskRow,
)
from .treemap import TreemapController

__all__ = [
    "CleanPreview",
    "DiskUsage",
    "ExportRow",
    "GrowthInfo",
    "GrowthItem",
    "MainController",
    "Mount",
    "PreviewItem",
    "PreviewResult",
    "SuggestionCleanPreview",
    "SuggestionController",
    "SuggestionRow",
    "TaskListController",
    "TaskRow",
    "TreemapController",
    "read_disk_usage",
]
