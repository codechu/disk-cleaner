"""Scanner Strategy temel tipleri.

Bir :class:`Scanner` ``list_tasks`` ile :class:`Task` üretir. Yeni bir tarama
türü eklemek için: ``Scanner`` alt sınıfı yaz, ``list_tasks`` döndür, registry'e
ekle. UI ve API bu ABC üzerinden konuşur — yeni scanner UI değişmeden çalışır.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING, Callable, Iterable, Literal, Optional

if TYPE_CHECKING:
    from ..cleaners.base import Cleaner

Risk = Literal["low", "medium", "high"]


@dataclass
class Task:
    """Tek bir temizlik adayı.

    ``size_fn`` tembel — yalnızca ihtiyaç anında çağrılır (du ağır).
    ``cleaner`` :class:`Cleaner` örneği; ``execute()`` ile uygulanır.
    """

    name: str
    desc: str
    risk: Risk
    path: str
    kind: str  # "system" | "artifact" | "duplicate" | "oldfile" | "empty" | ...
    size_fn: Callable[[], int]
    cleaner: "Cleaner"


class Scanner(ABC):
    """Bir tarama stratejisi — :class:`Task`'lar üretir."""

    name: str = "unknown"

    @abstractmethod
    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        """Bu kaynağın tüm ada Task'larını döndür.

        Args:
            cancel: Set edildiğinde uzun döngülerden erken çık.
            progress: Her küçük adımda kısa bir mesajla çağrılır
                (``ThrottledProgress`` ile sarmalanır).
        """


__all__ = ["Scanner", "Task", "Risk"]
