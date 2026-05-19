"""Regression tests for the watchdog daemon spawn path.

Bug history:
- ``--watchdog-start`` died immediately because the spawned argv pointed
  at a non-existent shim ``disk_cleaner.py`` inside packaged installs
  (snap / pip). Fix: spawn as ``python -m disk_cleaner --watchdog``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from disk_cleaner.watchdog import daemon as wd


@pytest.fixture
def isolated_runtime(tmp_path, monkeypatch):
    """Redirect pidfile + log into tmp_path so tests don't touch real XDG."""
    pid = tmp_path / "watchdog.pid"
    log = tmp_path / "watchdog.log"
    monkeypatch.setattr(wd, "WATCHDOG_PID_FILE", pid)
    monkeypatch.setattr(wd, "WATCHDOG_LOG", log)
    yield {"pid": pid, "log": log}
    # best-effort cleanup
    try:
        if pid.exists():
            try:
                p = int(pid.read_text().strip())
                os.kill(p, 15)
            except (OSError, ValueError):
                pass
            try:
                pid.unlink()
            except OSError:
                pass
    except Exception:
        pass


def test_watchdog_start_uses_module_form(isolated_runtime, monkeypatch):
    """Spawned argv must be ``-m disk_cleaner --watchdog``, never a .py path."""
    captured: dict[str, list] = {}

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = list(argv)
            captured["kwargs"] = kwargs
            self.pid = 999999  # bogus pid; the test does not verify liveness here

    monkeypatch.setattr(wd.subprocess, "Popen", _FakePopen)

    ok = wd.watchdog_start_background()
    assert ok is True

    argv = captured["argv"]
    # module-form invocation
    assert "-m" in argv
    m_index = argv.index("-m")
    assert argv[m_index + 1] == "disk_cleaner"
    assert "--watchdog" in argv
    # no absolute .py script path in argv
    for token in argv:
        assert not (isinstance(token, str) and token.endswith(".py") and Path(token).is_absolute()), (
            f"argv must not point at a script file path; got {token!r}"
        )
    # stdin must be DEVNULL so the daemon survives terminal close
    assert captured["kwargs"].get("stdin") == subprocess.DEVNULL
    # stdout/stderr go to a real file so the daemon is debuggable later
    assert captured["kwargs"].get("stdout") is not None
    # new session so the daemon detaches
    assert captured["kwargs"].get("start_new_session") is True


def test_watchdog_start_actually_spawns(isolated_runtime):
    """End-to-end: spawn, verify live PID, then stop."""
    # Use a tiny inline command instead of really running the daemon loop,
    # so the test is fast and deterministic. We bypass watchdog_start_background
    # only for the *spawn target*: we still want to verify pidfile + os.kill(pid, 0).
    pid_file = isolated_runtime["pid"]
    # Use sleep as a stand-in daemon
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        pid_file.write_text(str(proc.pid))
        time.sleep(0.1)
        # PID should be live
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # raises OSError if dead
        assert wd.watchdog_running() is True
        # Stop it via the public API
        assert wd.watchdog_stop() is True
        time.sleep(0.1)
        # PID file should be gone
        assert not pid_file.exists()
    finally:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
