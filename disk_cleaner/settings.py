"""Ayar deposu — JSON, atomic-ish, kararlı şema.

Modül seviyesinde paylaşılan ``SETTINGS`` dict UI ve mantık tarafından
ortak okunur/yazılır. Tam DI'a geçtikten sonra bu global :class:`SettingsStore`
örneğine dönüşecek; şimdilik geriye uyumluluk için kalır.

Şema (eski sürümle birebir uyumlu):

- ``trash_mode`` (bool)
- ``dry_run`` (bool)
- ``mount`` (str)
- ``entries`` (list[str])
- ``viz_mode`` ("treemap" | "sunburst")
- ``blacklist`` (list[str])
- ``watchdog_*`` (çeşitli)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import SETTINGS_DIR, SETTINGS_FILE


def load_settings() -> dict[str, Any]:
    """``settings.json``'u oku. Yoksa veya bozuksa boş dict."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data: dict[str, Any]) -> None:
    """``settings.json``'a yaz. Sessiz başarısızlık — diske yazılamasa da
    uygulama durmaz."""
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# Modül seviyesinde paylaşılan ayar sözlüğü.
SETTINGS: dict[str, Any] = load_settings()


def is_blacklisted(path: str) -> bool:
    """``SETTINGS['blacklist']`` altında varsa, bu yol önerilmez."""
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
    """JSON ayar deposu OOP yüzü (gelecekte DI için).

    Şu an modül-seviyesi ``SETTINGS`` paylaşımı korunur; ileride bu
    sınıf kendi ``_data``'sını tutarak global'i kaldıracak.
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
