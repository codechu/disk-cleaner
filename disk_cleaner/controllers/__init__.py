"""Presenter / Controller katmanı — View-bağımsız UI state machine'leri.

Tasarım sözleşmesi:

1. **Hiçbir GTK/Qt/HTML import yok.** Sadece domain modülleri
   (``viz``, ``core``, ``_tasks``, ``settings``, ``events``,
   ``runtime``, ``utils``) ve ``threading``/``time`` kullanılır.
2. **Observer pattern**: her controller ``on_*`` callable attribute'lerine
   sahiptir; View bunları register eder.
3. **Thread-safety**: callbacks worker thread'den de çağrılabilir; View
   kendi UI thread'ine marshalling'den sorumludur (Gtk için
   ``GLib.idle_add`` wrapper).
4. **Animation/hover/widget state View'da kalır** — controller yalnız
   data state machine.
5. **Headless test**: ``pytest`` controller'ı GUI olmadan koşturur.

Mevcut controller'lar:

- :class:`~disk_cleaner.controllers.main.MainController` — üst pencere
  kabuğu (mount, trash/dry, watchdog, disk usage)
- :class:`~disk_cleaner.controllers.treemap.TreemapController` — disk haritası
- :class:`~disk_cleaner.controllers.task_list.TaskListController` —
  tara/seç/temizle akışı (TaskPanel'in arkası)
- :class:`~disk_cleaner.controllers.suggestion.SuggestionController` —
  akıllı tarama + skor + grup + auto-select (SuggestionPanel'in arkası)
"""
from __future__ import annotations

from .main import DiskUsage, MainController, Mount, read_disk_usage
from .suggestion import (
    ExportRow,
    GrowthInfo,
    GrowthItem,
    SuggestionController,
    SuggestionRow,
)
from .suggestion import CleanPreview as SuggestionCleanPreview
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
