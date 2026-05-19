"""runtime module — TRASH_MODE + DRY_RUN state flags."""
from __future__ import annotations

import pytest

from disk_cleaner import runtime
from disk_cleaner.cleaners.command import CommandCleaner


def test_runtime_defaults():
    # Module-level defaults — not guarded by a fixture across tests to
    # avoid breaking isolation; type check only.
    assert isinstance(runtime.TRASH_MODE, bool)
    assert isinstance(runtime.DRY_RUN, bool)


def test_command_cleaner_reads_runtime_dry_run(monkeypatch):
    """The Cleaner must observe a runtime.DRY_RUN change at call time."""
    monkeypatch.setattr(runtime, "DRY_RUN", True)
    c = CommandCleaner(["echo", "this-should-not-run"])
    rc, out = c.execute()
    assert rc == 0
    assert "[DRY]" in out
    assert "echo" in out


def test_command_cleaner_executes_when_not_dry(monkeypatch):
    """When DRY_RUN is False, the real command runs."""
    monkeypatch.setattr(runtime, "DRY_RUN", False)
    c = CommandCleaner(["echo", "real-run"])
    rc, out = c.execute()
    assert rc == 0
    assert "real-run" in out
