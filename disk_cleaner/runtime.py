"""Runtime mutable globals.

Two state flags changed by the UI and read at call time by submodules:

- :data:`TRASH_MODE` — Trash mode. If True, ``gio trash`` is used
  instead of deletion (reversible).
- :data:`DRY_RUN` — Test mode. If True, cleanup commands are not
  executed; only "[DRY] would delete: …" is logged.

**Why a module global?** These values change at runtime via user
toggles but are read on almost every cleaner invocation. Instead of
propagating them via DI at every level, sharing them through one
state module is practical. New code should ``from .. import runtime``
and read ``runtime.TRASH_MODE`` at call time (not at import time —
late binding).

They can later be moved onto a typed accessor on
:class:`~disk_cleaner.settings.SettingsStore`.
"""
from __future__ import annotations

#: Trash mode (True → ``gio trash``, False → permanent deletion).
TRASH_MODE: bool = True

#: Dry-run (True → nothing is deleted, only logged).
DRY_RUN: bool = False


__all__ = ["DRY_RUN", "TRASH_MODE"]
