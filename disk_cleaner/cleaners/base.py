"""Cleaner Strategy temel sınıfı.

Bir :class:`Cleaner` ``execute()`` ile temizleme operasyonunu gerçekleştirir.
Yıkıcı işlemler **varsayılan olarak çöp kutusuna** gider; kalıcı silme
yalnızca kullanıcı açıkça istediğinde gerçekleşir.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Cleaner(ABC):
    """Bir temizlik stratejisi.

    Implementasyonlar :class:`SafePathCleaner`, :class:`ContentsCleaner`,
    :class:`CommandCleaner`, :class:`AptPurgeCleaner`, :class:`SnapCleaner`.
    Hepsi (returncode, mesaj) döndürür — UI özet gösterir, log detay tutar.
    """

    @abstractmethod
    def execute(self) -> tuple[int, str]:
        """Returns ``(returncode, message)``.

        ``returncode == 0`` başarı, diğerleri hata. ``message`` kullanıcıya
        gösterilebilir kısa metin.
        """


__all__ = ["Cleaner"]
