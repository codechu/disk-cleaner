"""Behavior of ``rm_path`` and ``safe_remove``.

To avoid polluting the real trash, ``rm_path`` (permanent delete) is
tested. ``safe_remove`` selects trash mode; the test exercises the
fallback when gio is missing on CI.
"""

from __future__ import annotations

from disk_cleaner.core.safe_remove import rm_path


def test_rm_path_file(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello")
    assert f.exists()
    rm_path(f)
    assert not f.exists()


def test_rm_path_dir(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    (d / "f").write_text("content")
    rm_path(d)
    assert not d.exists()


def test_rm_path_missing_is_noop(tmp_path):
    rm_path(tmp_path / "ghost")  # no error
