"""SystemScanner — sistem cache görevlerini :class:`Task` olarak yayınlar.

Mevcut ``SYSTEM_TASKS`` dict listesi (:mod:`disk_cleaner._tasks`) üstüne
ince bir Strategy adaptörü. İleride SYSTEM_TASKS doğrudan Task listesi
olacak; şimdilik dict şeması geriye uyumu için korunuyor.
"""
from __future__ import annotations

from threading import Event
from typing import Callable, Iterable, Optional

from ..cleaners.base import Cleaner
from ..i18n import _
from .base import Scanner, Task


class _CallableCleaner(Cleaner):
    """Eski ``clean_fn`` callable'ını :class:`Cleaner` arayüzüne sar."""

    def __init__(self, fn: Callable[[], tuple[int, str]], label: str = "") -> None:
        self._fn = fn
        self._label = label

    def execute(self) -> tuple[int, str]:
        return self._fn()


class SystemScanner(Scanner):
    """SYSTEM_TASKS dict listesini :class:`Task` akışına dönüştürür."""

    name = "system"

    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        from .. import _tasks

        for t in _tasks.SYSTEM_TASKS:
            if cancel is not None and cancel.is_set():
                break
            if progress is not None:
                progress(_("system: {name}").format(name=t["name"]))
            yield Task(
                name=t["name"],
                desc=t["desc"],
                risk=t["risk"],
                path=t["path"],
                kind="system",
                size_fn=t["size_fn"],
                cleaner=_CallableCleaner(t["clean_fn"], label=t["name"]),
            )


__all__ = ["SystemScanner"]
