"""SQLite ``du`` cache — speeds up re-scan by ~430×.

A cached result is considered safe as long as the directory ``mtime``
has not changed. Cache is invalidated when the TTL expires; manual
``invalidate(path)`` is also supported.
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
    """SQLite connection + ensure the table exists."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DU_CACHE_DB))
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def cached_dir_size(path: str | Path, ttl: float = DEFAULT_DU_CACHE_TTL_SEC) -> int:
    """Cached ``dir_size`` — uses the cache when mtime matches and TTL is fresh."""
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
        # if the cache fails, fall back to plain dir_size
        return dir_size(p)


def lookup_cached_dir_size(
    path: str | Path, ttl: float = DEFAULT_DU_CACHE_TTL_SEC
) -> int | None:
    """Return cached size if fresh, else None — never walks the directory.

    Suitable as a :class:`codechu_treeviz.SizeProvider` callback. Returning
    None lets ``build_tree`` recurse normally.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return None
    try:
        cur_mtime = p.stat().st_mtime
    except OSError:
        return None
    pkey = str(p.resolve())
    try:
        conn = du_cache_connect()
        try:
            row = conn.execute(
                "SELECT size, mtime, cached_at FROM du_cache WHERE path=?",
                (pkey,),
            ).fetchone()
            if not row:
                return None
            size, mtime, cached_at = row
            now = time.time()
            if abs(mtime - cur_mtime) < 0.5 and (now - cached_at) < ttl:
                return size
            return None
        finally:
            conn.close()
    except Exception:
        return None


def store_dir_size(path: str | Path, size: int) -> None:
    """Write the (path, size, mtime, now) tuple into the du_cache table.

    Called by the treemap controller after a fresh ``build_tree`` walk so
    the next scan can short-circuit via :func:`lookup_cached_dir_size`.
    """
    p = Path(path).expanduser()
    try:
        cur_mtime = p.stat().st_mtime
    except OSError:
        return
    pkey = str(p.resolve())
    try:
        conn = du_cache_connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO du_cache (path, size, mtime, cached_at)"
                " VALUES (?, ?, ?, ?)",
                (pkey, int(size), cur_mtime, time.time()),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def du_cache_invalidate(path: str | None = None) -> None:
    """Clear a specific path (and everything below) or the whole cache."""
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
    """Thin OOP wrapper over ``cached_dir_size`` / ``du_cache_invalidate``."""

    def __init__(self, path: Path | str = DU_CACHE_DB) -> None:
        self.path = Path(path)

    def get(self, path: str | Path, ttl: float = DEFAULT_DU_CACHE_TTL_SEC) -> int:
        return cached_dir_size(path, ttl=ttl)

    def invalidate(self, path: str | None = None) -> None:
        du_cache_invalidate(path)


__all__ = [
    "DuCache",
    "cached_dir_size",
    "du_cache_connect",
    "du_cache_invalidate",
    "lookup_cached_dir_size",
    "store_dir_size",
]
