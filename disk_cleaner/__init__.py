"""Disk Cleaner — modular package.

Public API:

- :class:`~disk_cleaner.app.AppContext` — composition root
- :mod:`~disk_cleaner.scanners` — Scanner Strategy (9 built-in + ABC)
- :mod:`~disk_cleaner.cleaners` — Cleaner Strategy (3 built-in + ABC)
- :mod:`~disk_cleaner.viz` — VizStrategy (treemap + sunburst)
- :mod:`~disk_cleaner.core` — saf domain mantığı
- :mod:`~disk_cleaner.storage` — DuCache + SnapshotStore
- :mod:`~disk_cleaner.settings` — SETTINGS + SettingsStore
- :mod:`~disk_cleaner.runtime` — TRASH_MODE / DRY_RUN (UI ↔ core kanalı)
- :mod:`~disk_cleaner.ui`, :mod:`~disk_cleaner.api`,
  :mod:`~disk_cleaner.watchdog` — UI / kontrol soketi / arka plan
- :mod:`~disk_cleaner.cli` — CLI dispatch + ``main()``
"""
from __future__ import annotations

__version__ = "0.1.0"

from .cli import cli_main, main  # noqa: F401

__all__ = ["__version__", "main", "cli_main"]
