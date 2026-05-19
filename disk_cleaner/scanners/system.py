"""SystemScanner — emit system cache tasks as :class:`Task` instances.

A thin Strategy adapter over the existing ``SYSTEM_TASKS`` dict list
(:mod:`disk_cleaner._tasks`). SYSTEM_TASKS becomes a direct Task list
later; for now the dict schema is kept for backwards compatibility.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from threading import Event

from ..cleaners.base import Cleaner
from ..i18n import _
from .base import Scanner, Task


class _CallableCleaner(Cleaner):
    """Wrap the legacy ``clean_fn`` callable in the :class:`Cleaner` interface."""

    def __init__(self, fn: Callable[[], tuple[int, str]], label: str = "") -> None:
        self._fn = fn
        self._label = label

    def execute(self) -> tuple[int, str]:
        return self._fn()


class SystemScanner(Scanner):
    """Convert the SYSTEM_TASKS dict list into a :class:`Task` stream."""

    name = "system"

    def list_tasks(
        self,
        *,
        cancel: Event | None = None,
        progress: Callable[[str], None] | None = None,
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
