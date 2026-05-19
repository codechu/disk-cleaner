"""SimilarImagesScanner — emit near-duplicate images via dHash + hamming."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from threading import Event

from .base import Scanner, Task
from .system import _CallableCleaner


class SimilarImagesScanner(Scanner):
    name = "similar"

    def __init__(self, folder: str | Path) -> None:
        self.folder = str(folder)

    def list_tasks(
        self,
        *,
        cancel: Event | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> Iterable[Task]:
        from .. import _tasks

        for t in _tasks.make_similar_image_tasks(self.folder, cancel=cancel, progress=progress):
            yield Task(
                name=t["name"],
                desc=t["desc"],
                risk=t["risk"],
                path=t["path"],
                kind="similar",
                size_fn=t["size_fn"],
                cleaner=_CallableCleaner(t["clean_fn"]),
            )


__all__ = ["SimilarImagesScanner"]
