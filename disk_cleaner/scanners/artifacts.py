"""ArtifactScanner — workspace altında build/cache artefaktları."""
from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Callable, Iterable, Optional

from .base import Scanner, Task
from .system import _CallableCleaner


class ArtifactScanner(Scanner):
    """``workspace_root`` altında node_modules / target / dist vb. bul.

    Aktif proje (.git mtime < ~14 gün) ise risk ``high``'a çıkar ve
    skorlayıcıda korunur.
    """

    name = "artifacts"

    def __init__(self, workspace_root: str | Path, active_threshold_days: int = 14) -> None:
        self.workspace_root = str(workspace_root)
        self.active_threshold_days = active_threshold_days

    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        from .. import _tasks

        tasks = _tasks.make_artifact_tasks(
            self.workspace_root,
            cancel=cancel,
            progress=progress,
            active_threshold_days=self.active_threshold_days,
        )
        for t in tasks:
            yield Task(
                name=t["name"],
                desc=t["desc"],
                risk=t["risk"],
                path=t["path"],
                kind="artifact",
                size_fn=t["size_fn"],
                cleaner=_CallableCleaner(t["clean_fn"]),
            )


__all__ = ["ArtifactScanner"]
