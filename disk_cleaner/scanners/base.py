"""Scanner Strategy base types.

A :class:`Scanner` yields :class:`Task` objects via ``list_tasks``. To
add a new scan type: write a ``Scanner`` subclass, return tasks from
``list_tasks``, and register it. UI and API speak to this ABC — a new
scanner works without UI changes.
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
    """A single cleanup candidate.

    ``size_fn`` is lazy — called only when needed (du is expensive).
    ``cleaner`` is a :class:`Cleaner` instance applied via ``execute()``.
    """

    name: str
    desc: str
    risk: Risk
    path: str
    kind: str  # "system" | "artifact" | "duplicate" | "oldfile" | "empty" | ...
    size_fn: Callable[[], int]
    cleaner: "Cleaner"


class Scanner(ABC):
    """A scanning strategy — yields :class:`Task` instances."""

    name: str = "unknown"

    @abstractmethod
    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        """Return all candidate Tasks for this source.

        Args:
            cancel: When set, exit long loops early.
            progress: Called with a short message at each small step
                (wrapped with ``ThrottledProgress``).
        """


__all__ = ["Scanner", "Task", "Risk"]
