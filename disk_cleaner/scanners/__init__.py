"""Scanner Strategy alt paketi.

Built-in scanner'lar (hepsi :class:`Scanner` alt sınıfı):

- :class:`SystemScanner` — ``SYSTEM_TASKS`` (cache, docker, apt, ...)
- :class:`ArtifactScanner` — workspace altında build artefaktları
- :class:`ExplorerScanner` — generic klasör gez
- :class:`OldFilesScanner` — Downloads benzeri eski dosyalar
- :class:`DuplicatesScanner` — aynı içerikli dosyalar
- :class:`EmptyScanner` — boş klasör / 0-byte dosya
- :class:`SimilarImagesScanner` — dHash + hamming yakın görseller
- :class:`AppUninstallScanner` — apt purge adayları
- :class:`UserRulesScanner` — kullanıcı tanımlı JSON kurallar

Yeni bir kaynak eklemek için :class:`Scanner` alt sınıfı yaz, registry'e
kaydet veya doğrudan :class:`~disk_cleaner.app.AppContext` üzerinden bağla.
"""
from __future__ import annotations

from typing import Dict

from .apps import AppUninstallScanner
from .artifacts import ArtifactScanner
from .base import Risk, Scanner, Task
from .duplicates import DuplicatesScanner
from .empty import EmptyScanner
from .explorer import ExplorerScanner
from .old_files import OldFilesScanner
from .similar import SimilarImagesScanner
from .system import SystemScanner
from .user_rules import UserRulesScanner


class ScannerRegistry:
    """İsim → Scanner örneği eşleştirmesi (plugin tarzı genişletme)."""

    def __init__(self) -> None:
        self._scanners: Dict[str, Scanner] = {}

    def register(self, name: str, scanner: Scanner) -> None:
        self._scanners[name] = scanner

    def get(self, name: str) -> Scanner:
        return self._scanners[name]

    def __iter__(self):
        return iter(self._scanners.items())

    def __contains__(self, name: str) -> bool:
        return name in self._scanners


__all__ = [
    "AppUninstallScanner",
    "ArtifactScanner",
    "DuplicatesScanner",
    "EmptyScanner",
    "ExplorerScanner",
    "OldFilesScanner",
    "Risk",
    "Scanner",
    "ScannerRegistry",
    "SimilarImagesScanner",
    "SystemScanner",
    "Task",
    "UserRulesScanner",
]
