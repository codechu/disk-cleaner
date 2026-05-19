"""Snapshot store — historical scan results + 7-day growth analysis.

Schema (kept bit-for-bit compatible with the legacy version):

- ``snapshots(id, scanned_at, mount, item_count, total_size)``
- ``items(snapshot_id, path, kind, size, score, risk)``

The most recent 20 snapshots are kept; older ones are pruned on write.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from ..config import SETTINGS_DIR, SNAPSHOTS_DB

_KEEP_SNAPSHOTS = 20
_GROWTH_DELTA_THRESHOLD = 50 * 1024 * 1024
_GROWTH_NEW_SIZE_THRESHOLD = 100 * 1024 * 1024

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    scanned_at REAL NOT NULL,
    mount TEXT,
    item_count INTEGER,
    total_size INTEGER
);
CREATE TABLE IF NOT EXISTS items (
    snapshot_id INTEGER,
    path TEXT,
    kind TEXT,
    size INTEGER,
    score INTEGER,
    risk TEXT,
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
);
CREATE INDEX IF NOT EXISTS idx_items_path ON items(path);
"""


def db_connect() -> sqlite3.Connection:
    """SQLite connection + ensure tables and indexes exist."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SNAPSHOTS_DB))
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def save_snapshot(items: list[dict[str, Any]], mount: str = "/") -> int | None:
    """``items``: list of ``{path, kind, size_bytes, score, risk}`` dicts."""
    conn = db_connect()
    try:
        cur = conn.execute(
            "INSERT INTO snapshots (scanned_at, mount, item_count, total_size) "
            "VALUES (?, ?, ?, ?)",
            (
                time.time(),
                mount,
                len(items),
                sum(int(i.get("size_bytes", 0)) for i in items),
            ),
        )
        sid = cur.lastrowid
        conn.executemany(
            "INSERT INTO items (snapshot_id, path, kind, size, score, risk) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    sid,
                    i.get("path", ""),
                    i.get("kind", ""),
                    int(i.get("size_bytes", 0)),
                    int(i.get("score", 0)),
                    i.get("risk", ""),
                )
                for i in items
            ],
        )
        conn.commit()
        # Prune old entries — keep only the last N snapshots.
        conn.execute(
            "DELETE FROM items WHERE snapshot_id IN "
            "(SELECT id FROM snapshots ORDER BY scanned_at DESC "
            f"LIMIT -1 OFFSET {_KEEP_SNAPSHOTS})"
        )
        conn.execute(
            "DELETE FROM snapshots WHERE id NOT IN "
            f"(SELECT id FROM snapshots ORDER BY scanned_at DESC LIMIT {_KEEP_SNAPSHOTS})"
        )
        conn.commit()
        return sid
    finally:
        conn.close()


def latest_snapshot_before(seconds_ago: float, mount: str = "/") -> dict[str, Any] | None:
    """Find the snapshot closest to ``seconds_ago`` seconds in the past (None if absent)."""
    conn = db_connect()
    try:
        cutoff = time.time() - seconds_ago
        cur = conn.execute(
            "SELECT id, scanned_at FROM snapshots "
            "WHERE scanned_at <= ? AND mount = ? "
            "ORDER BY scanned_at DESC LIMIT 1",
            (cutoff, mount),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "scanned_at": row[1]}
    finally:
        conn.close()


def snapshot_items(snapshot_id: int) -> dict[str, int]:
    """Return the ``{path: size}`` dict inside the snapshot."""
    conn = db_connect()
    try:
        cur = conn.execute(
            "SELECT path, size FROM items WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        return {path: size for path, size in cur.fetchall()}
    finally:
        conn.close()


def compute_growth(
    current_items: list[dict[str, Any]],
    mount: str = "/",
    days_back: int = 7,
) -> dict[str, Any] | None:
    """Compare the current scan against the one from ``days_back`` ago.

    Returns ``None`` if no historical snapshot exists yet; otherwise
    ``{prev_scanned_at, growth: [{path, name, current_size, prev_size,
    delta, ratio}, ...]}`` — growing items sorted by delta descending.
    """
    prev = latest_snapshot_before(days_back * 86400, mount)
    if not prev:
        return None
    prev_items = snapshot_items(prev["id"])
    growth: list[dict[str, Any]] = []
    for it in current_items:
        path = it.get("path", "")
        cur_size = int(it.get("size_bytes", 0))
        prev_size = prev_items.get(path, 0)
        delta = cur_size - prev_size
        if delta > _GROWTH_DELTA_THRESHOLD or (
            prev_size == 0 and cur_size > _GROWTH_NEW_SIZE_THRESHOLD
        ):
            ratio = (cur_size / prev_size) if prev_size > 0 else float("inf")
            growth.append({
                "path": path,
                "name": it.get("name", ""),
                "current_size": cur_size,
                "prev_size": prev_size,
                "delta": delta,
                "ratio": ratio,
            })
    growth.sort(key=lambda x: -x["delta"])
    return {"prev_scanned_at": prev["scanned_at"], "growth": growth}


class SnapshotStore:
    """Thin OOP wrapper over ``save_snapshot`` / growth functions."""

    def __init__(self, path: Path | str = SNAPSHOTS_DB) -> None:
        self.path = Path(path)

    def save(self, items: list[dict[str, Any]], mount: str = "/") -> int | None:
        return save_snapshot(items, mount=mount)

    def latest_before(
        self, seconds_ago: float, mount: str = "/"
    ) -> dict[str, Any] | None:
        return latest_snapshot_before(seconds_ago, mount=mount)

    def items(self, snapshot_id: int) -> dict[str, int]:
        return snapshot_items(snapshot_id)

    def growth(
        self,
        current_items: list[dict[str, Any]],
        mount: str = "/",
        days_back: int = 7,
    ) -> dict[str, Any] | None:
        return compute_growth(current_items, mount=mount, days_back=days_back)


__all__ = [
    "SnapshotStore",
    "compute_growth",
    "db_connect",
    "latest_snapshot_before",
    "save_snapshot",
    "snapshot_items",
]
