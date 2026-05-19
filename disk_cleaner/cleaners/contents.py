"""ContentsCleaner — bir dizinin içeriğini temizle (klasörü tutar)."""
from __future__ import annotations

from pathlib import Path

from ..core.safe_remove import rm_contents
from .base import Cleaner


class ContentsCleaner(Cleaner):
    """``rm_contents`` üstüne ince sarmalayıcı.

    ``force_permanent=True`` çöp kutusunu yoksayar (örn. çöp boşaltma
    akışında veya kullanıcı açıkça istediğinde).
    """

    def __init__(self, path: str | Path, force_permanent: bool = False) -> None:
        self.path = str(path)
        self.force_permanent = force_permanent

    def execute(self) -> tuple[int, str]:
        return rm_contents(self.path, force_permanent=self.force_permanent)


__all__ = ["ContentsCleaner"]
