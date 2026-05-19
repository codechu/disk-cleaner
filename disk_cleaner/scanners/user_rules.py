"""UserRulesScanner — emit rules from ``~/.config/disk_cleaner/cleaners/*.json``."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from threading import Event

from .base import Scanner, Task
from .system import _CallableCleaner


class UserRulesScanner(Scanner):
    """Convert user-defined cleaner JSON files into a Task stream."""

    name = "user_rules"

    def list_tasks(
        self,
        *,
        cancel: Event | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> Iterable[Task]:
        from .. import _tasks

        for t in _tasks.load_user_cleaners():
            yield Task(
                name=t["name"],
                desc=t["desc"],
                risk=t["risk"],
                path=t["path"],
                kind="user",
                size_fn=t["size_fn"],
                cleaner=_CallableCleaner(t["clean_fn"]),
            )


__all__ = ["UserRulesScanner"]
