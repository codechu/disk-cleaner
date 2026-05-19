"""Single source of constants and path definitions (XDG Base Directory Spec compliant).

No magic numbers / magic paths — look here.

**Vendor namespace.** All Codechu products live under a shared
``codechu/`` namespace on the user's disk. When future products like
``codechu/file-manager`` or ``codechu/system-monitor`` are added, a user
who opens that one directory finds every Codechu product. This follows
the same pattern as JetBrains' ``~/.config/JetBrains/`` or Mozilla's
``~/.mozilla/``.

XDG layout:
    config (settings, user rules)   → $XDG_CONFIG_HOME/codechu/disk-cleaner/
    cache  (regeneratable)          → $XDG_CACHE_HOME/codechu/disk-cleaner/
    data   (persistent, no regen)   → $XDG_DATA_HOME/codechu/disk-cleaner/
    runtime (pid, socket, lock)     → $XDG_RUNTIME_DIR/codechu/disk-cleaner/
"""

from __future__ import annotations

import os
from pathlib import Path

HOME: Path = Path.home()

# ---- XDG roots ----
XDG_CONFIG_HOME: Path = Path(os.environ.get("XDG_CONFIG_HOME", str(HOME / ".config")))
XDG_CACHE_HOME: Path = Path(os.environ.get("XDG_CACHE_HOME", str(HOME / ".cache")))
XDG_DATA_HOME: Path = Path(os.environ.get("XDG_DATA_HOME", str(HOME / ".local" / "share")))
XDG_RUNTIME_DIR: Path = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")

# ---- Vendor + product namespace ----
VENDOR = "codechu"
PRODUCT = "disk-cleaner"

SETTINGS_DIR: Path = XDG_CONFIG_HOME / VENDOR / PRODUCT  # config (settings, rules)
CACHE_DIR: Path = XDG_CACHE_HOME / VENDOR / PRODUCT  # regeneratable
DATA_DIR: Path = XDG_DATA_HOME / VENDOR / PRODUCT  # persistent data
RUNTIME_DIR: Path = XDG_RUNTIME_DIR / VENDOR / PRODUCT  # pid, socket, lock

# ---- Concrete files ----
SETTINGS_FILE: Path = SETTINGS_DIR / "settings.json"
USER_CLEANERS_DIR: Path = SETTINGS_DIR / "cleaners"

DU_CACHE_DB: Path = CACHE_DIR / "du_cache.db"  # disk usage cache — recomputed if lost
SNAPSHOTS_DB: Path = DATA_DIR / "snapshots.db"  # 7-day growth — user data, lost = gone

WATCHDOG_PID: Path = RUNTIME_DIR / "watchdog.pid"
CONTROL_SOCKET: str = str(RUNTIME_DIR / "control.sock")


def ensure_dirs() -> None:
    """Create all XDG-derived app directories (skip if they already exist)."""
    for d in (SETTINGS_DIR, CACHE_DIR, DATA_DIR, RUNTIME_DIR, USER_CLEANERS_DIR):
        d.mkdir(parents=True, exist_ok=True)


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

    migrations = {
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

    for old, new in migrations.items():
        if old.exists() and not new.exists():
            try:
                new.parent.mkdir(parents=True, exist_ok=True)
                old.replace(new)
            except OSError:
                pass

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
