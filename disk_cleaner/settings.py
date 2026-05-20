# SPDX-License-Identifier: GPL-3.0-or-later

"""Settings store — JSON, atomic-ish, stable schema.

The module-level shared ``SETTINGS`` dict is read/written by both the
UI and the logic layer. Once full DI is in place this global becomes a
:class:`SettingsStore` instance; it stays for backwards compatibility.

Schema (kept bit-for-bit compatible with the legacy version):

- ``trash_mode`` (bool)
- ``dry_run`` (bool)
- ``mount`` (str)
- ``entries`` (list[str])
- ``viz_mode`` ("treemap" | "sunburst")
- ``blacklist`` (list[str])
- ``watchdog_*`` (various)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import SETTINGS_DIR, SETTINGS_FILE


def load_settings() -> dict[str, Any]:
    """Read ``settings.json``. Empty dict if missing or corrupted."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data: dict[str, Any]) -> None:
    """Write to ``settings.json``. Fail silently — the app keeps running
    even if the file cannot be written."""
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# Module-level shared settings dict.
SETTINGS: dict[str, Any] = load_settings()


def is_blacklisted(path: str) -> bool:
    """If present in ``SETTINGS['blacklist']``, this path is not suggested."""
    if not path:
        return False
    bl = SETTINGS.get("blacklist", [])
    for entry in bl:
        if path == entry or path.startswith(entry.rstrip("/") + "/"):
            return True
    return False


def add_to_blacklist(path: str) -> None:
    bl = SETTINGS.setdefault("blacklist", [])
    if path and path not in bl:
        bl.append(path)
        save_settings(SETTINGS)


def remove_from_blacklist(path: str) -> None:
    bl = SETTINGS.get("blacklist", [])
    if path in bl:
        bl.remove(path)
        save_settings(SETTINGS)


class SettingsStore:
    """OOP front for the JSON settings store (DI handle).

    Currently the module-level ``SETTINGS`` sharing is preserved; this
    class can later own its ``_data`` and remove the global.
    """

    def __init__(self, path: Path | str = SETTINGS_FILE) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        return load_settings()

    def save(self, data: dict[str, Any]) -> None:
        save_settings(data)

    def get(self, key: str, default: Any = None) -> Any:
        return SETTINGS.get(key, default)

    def set(self, key: str, value: Any) -> None:
        SETTINGS[key] = value
        save_settings(SETTINGS)


__all__ = [
    "SETTINGS",
    "SettingsStore",
    "add_to_blacklist",
    "is_blacklisted",
    "load_settings",
    "remove_from_blacklist",
    "save_settings",
]
