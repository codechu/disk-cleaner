"""UI alt paketi — platform-spesifik View portları.

Mevcut portlar:

- :mod:`disk_cleaner.ui.gtk` — Linux desktop (GTK 3 + Cairo). Şu an
  varsayılan; ``cli.main()`` GUI moduna geçince bunu başlatır.

Planlanan portlar (her biri ``controllers/`` katmanına bağlanır):

- ``disk_cleaner.ui.qt`` — PyQt6 / PySide6 (cross-platform native)
- ``disk_cleaner.ui.web`` — pywebview + d3.js (en hafif cross-platform)
- ``disk_cleaner.ui.textual`` — terminal UI (headless makineler için)

Geriye uyumluluk için public sınıflar bu modülden de import edilebilir
(eski ``from disk_cleaner.ui.main_window import MainWindow`` çağrısı
yerine ``from disk_cleaner.ui.gtk import MainWindow``).
"""
from __future__ import annotations

from .gtk import (
    DynamicPanel,
    MainWindow,
    OldFilesPanel,
    RISK_COLORS,
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
