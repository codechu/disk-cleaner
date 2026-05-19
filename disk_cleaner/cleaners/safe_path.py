"""SafePathCleaner — tek bir yolu güvenli sil (çöp varsayılan).

Silme sonrası ``du_cache``'i invalidate eder; eski boyut UI'da kalmaz.
"""
from __future__ import annotations

from pathlib import Path

from ..core.safe_remove import safe_remove
from ..i18n import _
from ..storage.du_cache import du_cache_invalidate
from .base import Cleaner


class SafePathCleaner(Cleaner):
    """``safe_remove`` üstüne ince sarmalayıcı + cache invalidate."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    def execute(self) -> tuple[int, str]:
        try:
            result = safe_remove(Path(self.path))
        except Exception as e:
            return 1, _("error: {e}").format(e=e)
        try:
            resolved = str(Path(self.path).expanduser().resolve())
            du_cache_invalidate(resolved)
            du_cache_invalidate(str(Path(resolved).parent))
        except Exception:
            pass
        return 0, f"{self.path}: {result}"


__all__ = ["SafePathCleaner"]
