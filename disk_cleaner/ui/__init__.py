"""UI subpackage — platform-specific View ports.

Current ports:

- :mod:`disk_cleaner.ui.gtk` — Linux desktop (GTK 3 + Cairo). The
  default port; ``cli.main()`` launches it when entering GUI mode.

For backwards compatibility, public classes can be imported from this
module as well (the legacy
``from disk_cleaner.ui.main_window import MainWindow`` is replaced by
``from disk_cleaner.ui.gtk import MainWindow``).
"""

from __future__ import annotations

from .gtk import (
    RISK_COLORS,
    DynamicPanel,
    MainWindow,
    OldFilesPanel,
    SuggestionPanel,
    TaskPanel,
    TreemapPanel,
    try_init_tray,
)

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
