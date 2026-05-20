# SPDX-License-Identifier: GPL-3.0-or-later

"""Integration test: ``cached_dir_size`` second call must hit the cache.

Bug history: two consecutive ``--scan --sources system`` runs took the
same wall time. Re-verify that the SQLite cache layer:

1. Stores the freshly-computed size on first call.
2. Returns the cached value on the second call (no directory walk).
3. Produces identical sizes both times.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from disk_cleaner.storage import du_cache as du_cache_mod


def _build_tree(root: Path, *, file_count: int = 200, bytes_each: int = 5_000) -> int:
    """Create ``file_count`` small files under ``root``; return total bytes."""
    payload = b"x" * bytes_each
    for i in range(file_count):
        sub = root / f"d{i % 10}"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / f"f{i}.bin").write_bytes(payload)
    return file_count * bytes_each


def test_cached_dir_size_second_call_is_a_cache_hit(tmp_path, monkeypatch):
    cache_db = tmp_path / "cache.db"
    monkeypatch.setattr(du_cache_mod, "DU_CACHE_DB", cache_db)
    # The module also reaches up to ``SETTINGS_DIR`` for mkdir(); point that
    # at tmp_path too so the test stays sandboxed.
    monkeypatch.setattr(du_cache_mod, "SETTINGS_DIR", tmp_path / "settings")

    tree = tmp_path / "tree"
    tree.mkdir()
    expected = _build_tree(tree)

    # First call — populates the cache. Walks the tree.
    t0 = time.monotonic()
    size1 = du_cache_mod.cached_dir_size(tree)
    first_ms = (time.monotonic() - t0) * 1000

    # Second call — must hit the cache. No walk.
    t1 = time.monotonic()
    size2 = du_cache_mod.cached_dir_size(tree)
    second_ms = (time.monotonic() - t1) * 1000

    assert size1 == size2, "cache must return the same size on repeat"
    assert size1 >= expected, (
        f"reported size {size1} < expected {expected} — walk is incomplete"
    )

    # Cache hit ratio test. Relative if the first call was meaningfully
    # long, otherwise absolute.
    if first_ms > 100:
        assert second_ms < first_ms * 0.3, (
            f"second call ({second_ms:.1f}ms) not fast enough vs first "
            f"({first_ms:.1f}ms) — cache likely not hit"
        )
    else:
        assert second_ms < 50, (
            f"second call ({second_ms:.1f}ms) too slow for a cache hit "
            f"(first call was {first_ms:.1f}ms)"
        )

    # And the DB file actually exists with a row in it.
    assert cache_db.is_file(), "cache db was not persisted"
    import sqlite3

    with sqlite3.connect(str(cache_db)) as conn:
        rows = conn.execute("SELECT path, size FROM du_cache").fetchall()
    assert any(Path(p).resolve() == tree.resolve() for p, _s in rows), (
        f"expected a row for {tree}; got {rows}"
    )


def test_lookup_cached_dir_size_returns_none_before_populate(tmp_path, monkeypatch):
    cache_db = tmp_path / "cache.db"
    monkeypatch.setattr(du_cache_mod, "DU_CACHE_DB", cache_db)
    monkeypatch.setattr(du_cache_mod, "SETTINGS_DIR", tmp_path / "settings")
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "f").write_bytes(b"hello")
    # Before populate
    assert du_cache_mod.lookup_cached_dir_size(tree) is None
    # Populate
    du_cache_mod.cached_dir_size(tree)
    # Now should be a hit
    cached = du_cache_mod.lookup_cached_dir_size(tree)
    assert cached is not None and cached >= 5


@pytest.mark.parametrize("ttl", [0.0])
def test_expired_ttl_recomputes(tmp_path, monkeypatch, ttl):
    cache_db = tmp_path / "cache.db"
    monkeypatch.setattr(du_cache_mod, "DU_CACHE_DB", cache_db)
    monkeypatch.setattr(du_cache_mod, "SETTINGS_DIR", tmp_path / "settings")
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "f").write_bytes(b"x" * 100)
    s1 = du_cache_mod.cached_dir_size(tree, ttl=ttl)
    s2 = du_cache_mod.cached_dir_size(tree, ttl=ttl)
    assert s1 == s2
