"""runtime modülü — TRASH_MODE + DRY_RUN durum bayrakları."""
from __future__ import annotations

import pytest

from disk_cleaner import runtime
from disk_cleaner.cleaners.command import CommandCleaner


def test_runtime_defaults():
    # Modül-seviyesi default'lar — birden çok test arasında izolasyonu
    # bozmamak için fixture ile garanti edilmiyor; sadece tip kontrolü.
    assert isinstance(runtime.TRASH_MODE, bool)
    assert isinstance(runtime.DRY_RUN, bool)


def test_command_cleaner_reads_runtime_dry_run(monkeypatch):
    """Cleaner runtime.DRY_RUN değişikliğini çağrı anında görmeli."""
    monkeypatch.setattr(runtime, "DRY_RUN", True)
    c = CommandCleaner(["echo", "this-should-not-run"])
    rc, out = c.execute()
    assert rc == 0
    assert "[DRY]" in out
    assert "echo" in out


def test_command_cleaner_executes_when_not_dry(monkeypatch):
    """DRY_RUN False ise gerçek komut çalışır."""
    monkeypatch.setattr(runtime, "DRY_RUN", False)
    c = CommandCleaner(["echo", "real-run"])
    rc, out = c.execute()
    assert rc == 0
    assert "real-run" in out
