"""Tek noktadan sabitler ve yol tanımları (XDG Base Directory Spec uyumlu).

Magic number / magic path yok — buraya bak.

**Vendor namespace.** Tüm Codechu ürünleri kullanıcının diskinde ortak bir
``codechu/`` namespace altında yaşar. İleride ``codechu/file-manager``,
``codechu/system-monitor`` eklendiğinde tek dizini açan kullanıcı tüm
Codechu ürünlerini bulur. JetBrains'in ``~/.config/JetBrains/`` veya
Mozilla'nın ``~/.mozilla/`` deseniyle aynı.

XDG yerleşimi:
    config (settings, user rules)   → $XDG_CONFIG_HOME/codechu/disk-cleaner/
    cache  (regenerate edilebilir)  → $XDG_CACHE_HOME/codechu/disk-cleaner/
    data   (kalıcı, regenerate yok) → $XDG_DATA_HOME/codechu/disk-cleaner/
    runtime (pid, socket, lock)     → $XDG_RUNTIME_DIR/codechu/disk-cleaner/
"""
from __future__ import annotations

import os
from pathlib import Path

HOME: Path = Path.home()

# ---- XDG roots ----
XDG_CONFIG_HOME: Path = Path(os.environ.get("XDG_CONFIG_HOME", str(HOME / ".config")))
XDG_CACHE_HOME:  Path = Path(os.environ.get("XDG_CACHE_HOME",  str(HOME / ".cache")))
XDG_DATA_HOME:   Path = Path(os.environ.get("XDG_DATA_HOME",   str(HOME / ".local" / "share")))
XDG_RUNTIME_DIR: Path = Path(
    os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
)

# ---- Vendor + product namespace ----
VENDOR = "codechu"
PRODUCT = "disk-cleaner"

SETTINGS_DIR: Path = XDG_CONFIG_HOME / VENDOR / PRODUCT   # config (settings, rules)
CACHE_DIR:    Path = XDG_CACHE_HOME  / VENDOR / PRODUCT   # regenerate edilebilir
DATA_DIR:     Path = XDG_DATA_HOME   / VENDOR / PRODUCT   # kalıcı veri
RUNTIME_DIR:  Path = XDG_RUNTIME_DIR / VENDOR / PRODUCT   # pid, socket, lock

# ---- Concrete files ----
SETTINGS_FILE:     Path = SETTINGS_DIR / "settings.json"
USER_CLEANERS_DIR: Path = SETTINGS_DIR / "cleaners"

DU_CACHE_DB:  Path = CACHE_DIR / "du_cache.db"    # disk usage cache — kaybolursa yeniden hesaplanır
SNAPSHOTS_DB: Path = DATA_DIR  / "snapshots.db"   # 7-gün büyüme — kullanıcı verisi, kaybolursa geri gelmez

WATCHDOG_PID:    Path = RUNTIME_DIR / "watchdog.pid"
CONTROL_SOCKET:  str  = str(RUNTIME_DIR / "control.sock")


def ensure_dirs() -> None:
    """Tüm XDG-derived app dizinlerini oluştur (mevcutsa pas geç)."""
    for d in (SETTINGS_DIR, CACHE_DIR, DATA_DIR, RUNTIME_DIR, USER_CLEANERS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def migrate_pre_xdg_layout() -> None:
    """Önceki yerleşimlerden Codechu namespace'ine taşıma — idempotent.

    İki tarihsel layout var:
    1. v0.1-öncesi: her şey ``~/.config/disk_cleaner/`` altında
    2. v0.1: XDG-split ama vendor namespace yok (``~/.config/disk_cleaner/``,
       ``~/.cache/disk_cleaner/``, vs.)

    Bu fonksiyon ikisini de yeni layout'a (``codechu/disk-cleaner/``) taşır.
    """
    ensure_dirs()

    # Çift kaynak: legacy + v0.1-XDG (her ikisi de "disk_cleaner" dizin adı)
    legacy_config = XDG_CONFIG_HOME / "disk_cleaner"
    legacy_cache  = XDG_CACHE_HOME  / "disk_cleaner"
    legacy_data   = XDG_DATA_HOME   / "disk_cleaner"
    legacy_runtime = XDG_RUNTIME_DIR / "disk_cleaner"

    migrations = {
        # v0.1-öncesi (her şey config'de) + v0.1-XDG (config split)
        legacy_config / "settings.json": SETTINGS_FILE,
        legacy_config / "cleaners":      USER_CLEANERS_DIR,
        legacy_config / "du_cache.db":   DU_CACHE_DB,    # v0.1-öncesi
        legacy_config / "snapshots.db":  SNAPSHOTS_DB,
        legacy_config / "watchdog.pid":  WATCHDOG_PID,
        # v0.1-XDG paths
        legacy_cache   / "du_cache.db":  DU_CACHE_DB,
        legacy_data    / "snapshots.db": SNAPSHOTS_DB,
        legacy_data    / "watchdog.log": DATA_DIR / "watchdog.log",
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

    # Boş kalan legacy dizinleri sil (rmdir sadece boşsa siler — güvenli)
    for legacy_dir in (legacy_config, legacy_cache, legacy_data, legacy_runtime):
        if legacy_dir.exists():
            try:
                legacy_dir.rmdir()
            except OSError:
                pass  # boş değil veya başka sorun — bırak


TREEMAP_MAX_DEPTH: int = 40
DEFAULT_DU_CACHE_TTL_SEC: int = 6 * 3600
DEFAULT_MIN_SCORE: int = 40
DEFAULT_PROGRESS_HZ: int = 5
DEFAULT_RECURSION_LIMIT: int = 10000

# Otomatik temizlikten daima dışlanan kullanıcı veri yolları
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
    "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR",
    "VENDOR", "PRODUCT",
    "SETTINGS_DIR", "CACHE_DIR", "DATA_DIR", "RUNTIME_DIR",
    "SETTINGS_FILE",
    "DU_CACHE_DB",
    "SNAPSHOTS_DB",
    "WATCHDOG_PID",
    "USER_CLEANERS_DIR",
    "CONTROL_SOCKET",
    "ensure_dirs", "migrate_pre_xdg_layout",
    "TREEMAP_MAX_DEPTH",
    "DEFAULT_DU_CACHE_TTL_SEC",
    "DEFAULT_MIN_SCORE",
    "DEFAULT_PROGRESS_HZ",
    "DEFAULT_RECURSION_LIMIT",
    "USER_DATA_PATHS",
]
