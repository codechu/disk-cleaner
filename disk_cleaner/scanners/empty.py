"""EmptyScanner — emit empty directories and 0-byte files."""
from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Callable, Iterable, Optional

from .base import Scanner, Task
from .system import _CallableCleaner


class EmptyScanner(Scanner):
    name = "empty"

    def __init__(self, folder: str | Path) -> None:
        self.folder = str(folder)

    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        from .. import _tasks

        for t in _tasks.make_empty_tasks(self.folder, cancel=cancel, progress=progress):
            yield Task(
                name=t["name"],
                desc=t["desc"],
                risk=t["risk"],
                path=t["path"],
                kind="empty",
                size_fn=t["size_fn"],
                cleaner=_CallableCleaner(t["clean_fn"]),
            )


__all__ = ["EmptyScanner"]
