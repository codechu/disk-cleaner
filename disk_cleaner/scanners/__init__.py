"""Scanner Strategy subpackage.

Built-in scanners (all :class:`Scanner` subclasses):

- :class:`SystemScanner` — ``SYSTEM_TASKS`` (cache, docker, apt, ...)
- :class:`ArtifactScanner` — build artifacts under the workspace
- :class:`ExplorerScanner` — generic folder walker
- :class:`OldFilesScanner` — old files in Downloads-like folders
- :class:`DuplicatesScanner` — files with identical content
- :class:`EmptyScanner` — empty folders / 0-byte files
- :class:`SimilarImagesScanner` — dHash + hamming near-duplicate images
- :class:`AppUninstallScanner` — apt purge candidates
- :class:`UserRulesScanner` — user-defined JSON rules

To add a new source: write a :class:`Scanner` subclass and either
register it on the registry or wire it directly through
:class:`~disk_cleaner.app.AppContext`.
"""

from __future__ import annotations

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
    """Name → Scanner instance mapping (plugin-style extension)."""

    def __init__(self) -> None:
        self._scanners: dict[str, Scanner] = {}

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
