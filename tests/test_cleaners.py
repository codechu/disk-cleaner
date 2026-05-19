"""Behavior tests for Cleaner classes."""

from __future__ import annotations

from disk_cleaner.cleaners import (
    Cleaner,
    CommandCleaner,
    ContentsCleaner,
    SafePathCleaner,
)


def test_cleaners_implement_abc():
    for cls in (SafePathCleaner, ContentsCleaner, CommandCleaner):
        assert issubclass(cls, Cleaner)


def test_safe_path_cleaner_missing_path(tmp_path):
    c = SafePathCleaner(tmp_path / "ghost")
    rc, msg = c.execute()
    # safe_remove returns "missing, skipped"; not a failure
    assert rc == 0
    assert "skipped" in msg or "ghost" in msg


def test_contents_cleaner_missing_path(tmp_path):
    c = ContentsCleaner(tmp_path / "ghost")
    rc, msg = c.execute()
    assert rc == 0
    assert "not found" in msg


def test_contents_cleaner_actually_removes(tmp_path):
    (tmp_path / "a.bin").write_text("x")
    (tmp_path / "b.bin").write_text("y")
    c = ContentsCleaner(tmp_path, force_permanent=True)
    rc, msg = c.execute()
    assert rc == 0
    assert "2 items" in msg
    assert list(tmp_path.iterdir()) == []


def test_command_cleaner_runs_echo():
    c = CommandCleaner(["echo", "hello"])
    rc, out = c.execute()
    assert rc == 0
    assert "hello" in out


def test_command_cleaner_dry_run(monkeypatch):
    from disk_cleaner import runtime

    monkeypatch.setattr(runtime, "DRY_RUN", True)
    c = CommandCleaner(["rm", "-rf", "/"])  # would be catastrophic — but DRY_RUN
    rc, out = c.execute()
    assert rc == 0
    assert "[DRY]" in out


def test_command_cleaner_shell_string():
    c = CommandCleaner("echo from-shell", shell=True)
    rc, out = c.execute()
    assert rc == 0
    assert "from-shell" in out
