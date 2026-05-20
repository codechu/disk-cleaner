"""Single source of constants and path definitions (XDG Base Directory Spec compliant).

No magic numbers / magic paths — look here.

**Vendor namespace.** All Codechu products live under a shared
``codechu/`` namespace on the user's disk. When future products like
``codechu/file-manager`` or ``codechu/system-monitor`` are added, a user
who opens that one directory finds every Codechu product. This follows
the same pattern as JetBrains' ``~/.config/JetBrains/`` or Mozilla's
``~/.mozilla/``.

XDG layout (computed by :mod:`codechu_xdg`):
    config (settings, user rules)   → $XDG_CONFIG_HOME/codechu/disk-cleaner/
    cache  (regeneratable)          → $XDG_CACHE_HOME/codechu/disk-cleaner/
    data   (persistent, no regen)   → $XDG_DATA_HOME/codechu/disk-cleaner/
    runtime (pid, socket, lock)     → $XDG_RUNTIME_DIR/codechu/disk-cleaner/
"""

from __future__ import annotations

import os
from pathlib import Path

from codechu_xdg import App, cache_home, config_home, data_home, default_env, runtime_dir

HOME: Path = Path.home()

# ---- Vendor + product namespace ----
VENDOR = "codechu"
PRODUCT = "disk-cleaner"

# Application-level App instance. ``default_env()`` snapshots the real
# environment at import time, matching the previous behaviour of the
# v0.1 module-level XDG_* constants.
_env = default_env()
_uid = os.getuid()
_app = App(vendor=VENDOR, product=PRODUCT, env=_env, uid=_uid)

# ---- XDG base directories (vendor-neutral; used for legacy migration) ----
XDG_CONFIG_HOME: Path = config_home(_env)
XDG_CACHE_HOME: Path = cache_home(_env)
XDG_DATA_HOME: Path = data_home(_env)
XDG_RUNTIME_DIR: Path = runtime_dir(_env, _uid)

# ---- XDG-derived application directories (back-compat exports) ----
SETTINGS_DIR: Path = _app.config_dir  # config (settings, rules)
CACHE_DIR: Path = _app.cache_dir  # regeneratable
DATA_DIR: Path = _app.data_dir  # persistent data
RUNTIME_DIR: Path = _app.runtime_dir  # pid, socket, lock

# ---- Concrete files ----
SETTINGS_FILE: Path = _app.settings_file("settings.json")
USER_CLEANERS_DIR: Path = _app.config_dir / "cleaners"

DU_CACHE_DB: Path = _app.cache_file("du_cache.db")  # disk usage cache — recomputed if lost
SNAPSHOTS_DB: Path = _app.data_file("snapshots.db")  # 7-day growth — user data, lost = gone

WATCHDOG_PID: Path = _app.runtime_file("watchdog.pid")
CONTROL_SOCKET: str = str(_app.runtime_file("control.sock"))


def ensure_dirs() -> None:
    """Create all XDG-derived app directories (skip if they already exist)."""
    _app.ensure()
    USER_CLEANERS_DIR.mkdir(parents=True, exist_ok=True)


def migrate_pre_xdg_layout() -> None:
    """Migrate from previous layouts to the Codechu namespace — idempotent.

    Two historical layouts exist:
    1. pre-v0.1: everything under ``~/.config/disk_cleaner/``
    2. v0.1: XDG-split but no vendor namespace (``~/.config/disk_cleaner/``,
       ``~/.cache/disk_cleaner/``, etc.)

    This function moves both into the new layout (``codechu/disk-cleaner/``).
    """
    ensure_dirs()

    # Dual source: legacy + v0.1-XDG (both use the "disk_cleaner" directory name)
    legacy_config = XDG_CONFIG_HOME / "disk_cleaner"
    legacy_cache = XDG_CACHE_HOME / "disk_cleaner"
    legacy_data = XDG_DATA_HOME / "disk_cleaner"
    legacy_runtime = XDG_RUNTIME_DIR / "disk_cleaner"

    mapping = {
        # pre-v0.1 (everything in config) + v0.1-XDG (config split)
        legacy_config / "settings.json": SETTINGS_FILE,
        legacy_config / "cleaners": USER_CLEANERS_DIR,
        legacy_config / "du_cache.db": DU_CACHE_DB,  # pre-v0.1
        legacy_config / "snapshots.db": SNAPSHOTS_DB,
        legacy_config / "watchdog.pid": WATCHDOG_PID,
        # v0.1-XDG paths
        legacy_cache / "du_cache.db": DU_CACHE_DB,
        legacy_data / "snapshots.db": SNAPSHOTS_DB,
        legacy_data / "watchdog.log": DATA_DIR / "watchdog.log",
        legacy_runtime / "watchdog.pid": WATCHDOG_PID,
        legacy_runtime / "control.sock": Path(CONTROL_SOCKET),
    }

    _app.migrate(mapping)

    # Remove empty legacy directories (rmdir only deletes if empty — safe)
    for legacy_dir in (legacy_config, legacy_cache, legacy_data, legacy_runtime):
        if legacy_dir.exists():
            try:
                legacy_dir.rmdir()
            except OSError:
                pass  # not empty or some other issue — leave it


TREEMAP_MAX_DEPTH: int = 40
DEFAULT_DU_CACHE_TTL_SEC: int = 6 * 3600
DEFAULT_MIN_SCORE: int = 40
DEFAULT_PROGRESS_HZ: int = 5
DEFAULT_RECURSION_LIMIT: int = 10000

# User data paths always excluded from automatic cleanup
USER_DATA_PATHS: tuple[str, ...] = (
    "~/Documents",
    "~/Pictures",
    "~/Videos",
    "~/Music",
    "~/Desktop",
    "~/workspace",
)


__all__ = [
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "XDG_RUNTIME_DIR",
    "VENDOR",
    "PRODUCT",
    "SETTINGS_DIR",
    "CACHE_DIR",
    "DATA_DIR",
    "RUNTIME_DIR",
    "SETTINGS_FILE",
    "DU_CACHE_DB",
    "SNAPSHOTS_DB",
    "WATCHDOG_PID",
    "USER_CLEANERS_DIR",
    "CONTROL_SOCKET",
    "ensure_dirs",
    "migrate_pre_xdg_layout",
    "TREEMAP_MAX_DEPTH",
    "DEFAULT_DU_CACHE_TTL_SEC",
    "DEFAULT_MIN_SCORE",
    "DEFAULT_PROGRESS_HZ",
    "DEFAULT_RECURSION_LIMIT",
    "USER_DATA_PATHS",
]
