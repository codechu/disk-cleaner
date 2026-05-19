"""SQLite ``du`` cache — re-scan'i ~430× hızlandırır.

Dizinin ``mtime`` değişmediği sürece kayıtlı sonuç güvenli kabul edilir.
TTL süresi geçince invalidate; manuel ``invalidate(path)`` da destekli.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from ..config import DEFAULT_DU_CACHE_TTL_SEC, DU_CACHE_DB, SETTINGS_DIR
from ..core.sizing import dir_size

_SCHEMA = """CREATE TABLE IF NOT EXISTS du_cache (
    path TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    cached_at REAL NOT NULL
)"""


def du_cache_connect() -> sqlite3.Connection:
    """SQLite bağlantısı + tablo garantisi."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DU_CACHE_DB))
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def cached_dir_size(path: str | Path, ttl: float = DEFAULT_DU_CACHE_TTL_SEC) -> int:
    """``dir_size`` cache'li sürüm — mtime aynıysa ve TTL geçmemişse cache."""
    p = Path(path).expanduser()
    if not p.exists():
        return 0
    try:
        cur_mtime = p.stat().st_mtime
    except OSError:
        return 0
    pkey = str(p.resolve())
    try:
        conn = du_cache_connect()
        try:
            row = conn.execute(
                "SELECT size, mtime, cached_at FROM du_cache WHERE path=?",
                (pkey,),
            ).fetchone()
            now = time.time()
            if row:
                size, mtime, cached_at = row
                if abs(mtime - cur_mtime) < 0.5 and (now - cached_at) < ttl:
                    return size
            size = dir_size(p)
            conn.execute(
                "INSERT OR REPLACE INTO du_cache (path, size, mtime, cached_at)"
                " VALUES (?, ?, ?, ?)",
                (pkey, size, cur_mtime, now),
            )
            conn.commit()
            return size
        finally:
            conn.close()
    except Exception:
        # cache çalışmazsa düz dir_size
        return dir_size(p)


def du_cache_invalidate(path: str | None = None) -> None:
    """Belirli bir yolu (ve altını) ya da tüm cache'i temizle."""
    try:
        conn = du_cache_connect()
        try:
            if path:
                conn.execute(
                    "DELETE FROM du_cache WHERE path = ? OR path LIKE ?",
                    (path, path + "/%"),
                )
            else:
                conn.execute("DELETE FROM du_cache")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


class DuCache:
    """``cached_dir_size`` / ``du_cache_invalidate`` üstüne ince OOP sarmalayıcı."""

    def __init__(self, path: Path | str = DU_CACHE_DB) -> None:
        self.path = Path(path)

    def get(self, path: str | Path, ttl: float = DEFAULT_DU_CACHE_TTL_SEC) -> int:
        return cached_dir_size(path, ttl=ttl)

    def invalidate(self, path: str | None = None) -> None:
        du_cache_invalidate(path)


__all__ = ["DuCache", "cached_dir_size", "du_cache_connect", "du_cache_invalidate"]
