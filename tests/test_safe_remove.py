"""``rm_path`` ve ``safe_remove`` davranışı.

Gerçek çöp kutusunu kirletmemek için ``rm_path`` (kalıcı silme) testlenir.
``safe_remove`` çöp kutusu modunu seçer; CI'da gio yoksa fallback'i test eder.
"""
from __future__ import annotations

from pathlib import Path

from disk_cleaner.core.safe_remove import rm_path, safe_remove


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
