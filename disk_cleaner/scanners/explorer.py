"""ExplorerScanner — bir klasörün bir-seviye çocuklarını Task olarak yayınla."""
from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Callable, Iterable, Optional

from .base import Scanner, Task
from .system import _CallableCleaner


class ExplorerScanner(Scanner):
    """Treemap / "klasörü gez" akışı için generic dinamik tarayıcı."""

    name = "explorer"

    def __init__(self, folder: str | Path) -> None:
        self.folder = str(folder)

    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        from .. import _tasks

        for t in _tasks.make_folder_explorer_tasks(self.folder, cancel=cancel):
            yield Task(
                name=t["name"],
                desc=t["desc"],
                risk=t["risk"],
                path=t["path"],
                kind="explorer",
                size_fn=t["size_fn"],
                cleaner=_CallableCleaner(t["clean_fn"]),
            )


__all__ = ["ExplorerScanner"]
