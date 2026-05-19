"""OldFilesScanner — emit a folder's children older than ``days`` days."""
from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Callable, Iterable, Optional

from .base import Scanner, Task
from .system import _CallableCleaner


class OldFilesScanner(Scanner):
    """A Downloads-like folder + age threshold → old-file tasks."""

    name = "old_files"

    def __init__(self, folder: str | Path, days: int = 90) -> None:
        self.folder = str(folder)
        self.days = days

    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        from .. import _tasks

        for t in _tasks.make_old_files_tasks(self.folder, self.days, cancel=cancel):
            yield Task(
                name=t["name"],
                desc=t["desc"],
                risk=t["risk"],
                path=t["path"],
                kind="oldfile",
                size_fn=t["size_fn"],
                cleaner=_CallableCleaner(t["clean_fn"]),
            )


__all__ = ["OldFilesScanner"]
