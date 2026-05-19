"""Real du / path_size behavior over temporary directories."""
from __future__ import annotations

from pathlib import Path

from disk_cleaner.core.sizing import dir_size, path_size


def test_dir_size_empty_path(tmp_path):
    assert dir_size(tmp_path) >= 0


def test_dir_size_with_content(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 4096)
    (tmp_path / "b.bin").write_bytes(b"y" * 4096)
    size = dir_size(tmp_path)
    # du reports in blocks — at least ~8KB, leave some headroom for FS overhead
    assert size >= 4096


def test_path_size_file(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"z" * 2048)
    assert path_size(f) > 0


def test_path_size_missing_returns_zero(tmp_path):
    assert path_size(tmp_path / "does-not-exist") == 0
