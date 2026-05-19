"""Snapshot deposu — geçmiş tarama sonuçları + 7-gün büyüme analizi.

Şema (eski sürümle birebir uyumlu):

- ``snapshots(id, scanned_at, mount, item_count, total_size)``
- ``items(snapshot_id, path, kind, size, score, risk)``

En son 20 snapshot tutulur; daha eskileri yazımda budanır.
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
    """SQLite bağlantısı + tablo/indeks garantisi."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SNAPSHOTS_DB))
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def save_snapshot(items: list[dict[str, Any]], mount: str = "/") -> int | None:
    """``items``: ``{path, kind, size_bytes, score, risk}`` dict listesi."""
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
        # Eskileri buda — yalnızca son N snapshot kalsın.
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
    """``seconds_ago`` sn öncesindeki en yakın snapshot'ı bul (yoksa None)."""
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
    """Snapshot içindeki ``{path: size}`` dict'i döndür."""
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
    """Mevcut taramayı ``days_back`` gün önceki ile karşılaştır.

    Returns ``None`` if no historical snapshot exists yet; otherwise
    ``{prev_scanned_at, growth: [{path, name, current_size, prev_size,
    delta, ratio}, ...]}`` — büyüyen öğeler delta'ya göre azalan sırada.
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
    """``save_snapshot`` / growth fonksiyonları üstüne ince OOP sarmalayıcı."""

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
