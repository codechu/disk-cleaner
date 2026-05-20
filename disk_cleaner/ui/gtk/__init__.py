# SPDX-License-Identifier: GPL-3.0-or-later

"""GTK port — Linux desktop View.

The current port. All widgets get their services from the
``controllers/`` layer.

Public classes (used by CLI ``main()`` and the API):

- :class:`MainWindow` + :func:`try_init_tray`
- :class:`SuggestionPanel`
- :class:`TaskPanel`
- :class:`DynamicPanel`
- :class:`OldFilesPanel`
- :class:`TreemapPanel`
"""

from __future__ import annotations

from .dynamic_panel import DynamicPanel
from .main_window import MainWindow, try_init_tray
from .old_files_panel import OldFilesPanel
from .suggestion_panel import SuggestionPanel
from .task_panel import TaskPanel
from .treemap_panel import TreemapPanel
from .widgets import RISK_COLORS

__all__ = [
    "DynamicPanel",
    "MainWindow",
    "OldFilesPanel",
    "RISK_COLORS",
    "SuggestionPanel",
    "TaskPanel",
    "TreemapPanel",
    "try_init_tray",
]
