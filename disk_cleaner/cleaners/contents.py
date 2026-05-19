"""ContentsCleaner — clear a directory's contents (keep the directory)."""
from __future__ import annotations

from pathlib import Path

from ..core.safe_remove import rm_contents
from .base import Cleaner


class ContentsCleaner(Cleaner):
    """Thin wrapper over ``rm_contents``.

    ``force_permanent=True`` ignores the trash (e.g. during a trash-empty
    flow or when the user explicitly requests it).
    """

    def __init__(self, path: str | Path, force_permanent: bool = False) -> None:
        self.path = str(path)
        self.force_permanent = force_permanent

    def execute(self) -> tuple[int, str]:
        return rm_contents(self.path, force_permanent=self.force_permanent)


__all__ = ["ContentsCleaner"]
