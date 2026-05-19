"""AppUninstallScanner — apt purge + related folder cleanup candidates."""
from __future__ import annotations

from threading import Event
from typing import Callable, Iterable, Optional

from .base import Scanner, Task
from .system import _CallableCleaner


class AppUninstallScanner(Scanner):
    """Emit the top 80 installed apt packages by size as ``risk=high`` Tasks."""

    name = "apps"

    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        from .. import _tasks

        for t in _tasks.make_app_uninstall_tasks(cancel=cancel, progress=progress):
            yield Task(
                name=t["name"],
                desc=t["desc"],
                risk=t["risk"],
                path=t["path"],
                kind="app",
                size_fn=t["size_fn"],
                cleaner=_CallableCleaner(t["clean_fn"]),
            )


__all__ = ["AppUninstallScanner"]
