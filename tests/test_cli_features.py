"""Tests for the new CLI features added to disk_cleaner.cli.

Covers:
- ``--version``
- settings ``--set / --get / --list-settings``
- custom cleaner ``--list-cleaners / --add-cleaner / --remove-cleaner``
- snapshot ``--snapshot create | list | diff``
- ``--export-treemap`` (smoke test via cairo)

These run in-process via ``cli_main`` and use a tmp XDG layout so they
don't touch the user's real config / data dirs.
"""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def xdg_env(tmp_path, monkeypatch):
    """Re-point all XDG dirs at tmp_path and reload config-dependent modules."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    for sub in ("config", "data", "cache", "runtime"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)

    # Reload disk_cleaner.config so its App / XDG_* snapshot picks up
    # the patched environment (codechu_xdg 0.2 has no module-level
    # constants; only the App instance and helpers, which read env
    # explicitly).
    from disk_cleaner import config as dc_config

    importlib.reload(dc_config)
    from disk_cleaner.storage import snapshots as dc_snapshots

    importlib.reload(dc_snapshots)
    from disk_cleaner import cli as dc_cli

    importlib.reload(dc_cli)
    dc_config.ensure_dirs()
    # Reset shared mutable runtime state so tests don't bleed into each other.
    from disk_cleaner import runtime as dc_runtime

    dc_runtime.DRY_RUN = False
    dc_runtime.TRASH_MODE = True
    yield dc_cli, dc_config
    # Reload once more so other tests see a fresh, env-fresh state.
    importlib.reload(dc_config)
    importlib.reload(dc_cli)


def _capture(monkeypatch):
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    return out, err


# ---------- --version ----------


def test_version_flag(xdg_env, monkeypatch):
    cli, _ = xdg_env
    out, err = _capture(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        cli.cli_main(["--version"])
    assert exc.value.code == 0
    combined = out.getvalue() + err.getvalue()
    assert "Disk Cleaner" in combined and "0.1.0" in combined


# ---------- settings ----------


def test_set_get_list_settings_roundtrip(xdg_env, monkeypatch):
    cli, config = xdg_env
    out, err = _capture(monkeypatch)
    assert cli.cli_main(["--set", "language=tr"]) == 0
    out.truncate(0)
    out.seek(0)
    err.truncate(0)
    err.seek(0)
    assert cli.cli_main(["--get", "language"]) == 0
    assert out.getvalue().strip() == "tr"

    # Dotted key — nested write
    assert cli.cli_main(["--set", "watchdog.threshold=5G"]) == 0
    data = json.loads(config.SETTINGS_FILE.read_text())
    assert data["watchdog"]["threshold"] == "5G"

    # list-settings includes all known keys
    out.truncate(0)
    out.seek(0)
    assert cli.cli_main(["--list-settings"]) == 0
    text = out.getvalue()
    for k in ("language", "theme", "viz_mode", "watchdog.threshold", "watchdog.interval"):
        assert k in text


def test_set_unknown_key_exits_2(xdg_env, monkeypatch):
    cli, _ = xdg_env
    _capture(monkeypatch)
    assert cli.cli_main(["--set", "bogus=1"]) == 2


def test_set_invalid_choice_exits_2(xdg_env, monkeypatch):
    cli, _ = xdg_env
    _capture(monkeypatch)
    assert cli.cli_main(["--set", "language=de"]) == 2


def test_set_invalid_int_exits_2(xdg_env, monkeypatch):
    cli, _ = xdg_env
    _capture(monkeypatch)
    assert cli.cli_main(["--set", "watchdog.interval=abc"]) == 2


def test_get_missing_key_exits_1(xdg_env, monkeypatch):
    cli, _ = xdg_env
    _capture(monkeypatch)
    assert cli.cli_main(["--get", "theme"]) == 1


# ---------- cleaners ----------


def _write_cleaner_json(path: Path, name: str, paths=("~/.x",), desc="hi"):
    path.write_text(json.dumps({
        "name": name,
        "desc": desc,
        "risk": "low",
        "paths": list(paths),
    }))


def test_list_cleaners_empty(xdg_env, monkeypatch):
    cli, _ = xdg_env
    out, err = _capture(monkeypatch)
    assert cli.cli_main(["--list-cleaners"]) == 0
    assert "No custom cleaners" in out.getvalue()


def test_add_list_remove_cleaner(tmp_path, xdg_env, monkeypatch):
    cli, config = xdg_env
    src = tmp_path / "my.json"
    _write_cleaner_json(src, "MyCleaner")
    _capture(monkeypatch)
    assert cli.cli_main(["--add-cleaner", str(src)]) == 0
    installed = config.USER_CLEANERS_DIR / "MyCleaner.json"
    assert installed.exists()

    out, _err = _capture(monkeypatch)
    assert cli.cli_main(["--list-cleaners"]) == 0
    assert "MyCleaner" in out.getvalue()

    _capture(monkeypatch)
    assert cli.cli_main(["--remove-cleaner", "MyCleaner"]) == 0
    assert not installed.exists()


def test_add_cleaner_refuses_overwrite_without_force(tmp_path, xdg_env, monkeypatch):
    cli, config = xdg_env
    src = tmp_path / "my.json"
    _write_cleaner_json(src, "DupCleaner")
    _capture(monkeypatch)
    assert cli.cli_main(["--add-cleaner", str(src)]) == 0
    _capture(monkeypatch)
    assert cli.cli_main(["--add-cleaner", str(src)]) == 1
    _capture(monkeypatch)
    assert cli.cli_main(["--add-cleaner", str(src), "--force"]) == 0


def test_add_cleaner_validates_schema(tmp_path, xdg_env, monkeypatch):
    cli, _ = xdg_env
    # Missing name
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"paths": ["/tmp"]}))
    _capture(monkeypatch)
    assert cli.cli_main(["--add-cleaner", str(bad)]) == 1

    # Missing paths AND command
    bad2 = tmp_path / "bad2.json"
    bad2.write_text(json.dumps({"name": "x"}))
    _capture(monkeypatch)
    assert cli.cli_main(["--add-cleaner", str(bad2)]) == 1


def test_remove_cleaner_missing_exits_1(xdg_env, monkeypatch):
    cli, _ = xdg_env
    _capture(monkeypatch)
    assert cli.cli_main(["--remove-cleaner", "nope"]) == 1


# ---------- --items ----------


def test_clean_items_no_match_exits_2(xdg_env, monkeypatch):
    cli, _ = xdg_env
    # Empty enriched list — no tasks match "ghost".
    monkeypatch.setattr(cli, "cli_collect_tasks", lambda *a, **kw: [])
    _capture(monkeypatch)
    assert cli.cli_main(["--clean", "--items", "ghost", "--dry-run", "-y"]) == 2


def test_clean_items_matches(xdg_env, monkeypatch):
    cli, _ = xdg_env
    called = {"n": 0}

    def fake_clean():
        called["n"] += 1
        return 0, ""

    fake_task = {
        "name": "fake-task",
        "path": "/x",
        "kind": "system",
        "size_bytes": 100,
        "size_human": "100 B",
        "score": 80,
        "reason": "ok",
        "risk": "low",
        "_task": {"name": "fake-task", "clean_fn": fake_clean},
    }
    monkeypatch.setattr(cli, "cli_collect_tasks", lambda *a, **kw: [fake_task])
    _capture(monkeypatch)
    rc = cli.cli_main(["--clean", "--items", "fake-task", "-y"])
    assert rc == 0
    assert called["n"] == 1


# ---------- snapshot ----------


def test_snapshot_list_empty(xdg_env, monkeypatch):
    cli, _ = xdg_env
    out, err = _capture(monkeypatch)
    assert cli.cli_main(["--snapshot", "list"]) == 0
    assert "No snapshots" in (out.getvalue() + err.getvalue())


def test_snapshot_create_then_list(xdg_env, monkeypatch):
    cli, _ = xdg_env
    # Stub SYSTEM_TASKS with one task that returns a known size.
    from disk_cleaner import _tasks as tasks_mod

    fake = {
        "name": "Test",
        "path": "/tmp/x",
        "risk": "low",
        "size_fn": lambda: 1024,
        "clean_fn": lambda: (0, ""),
    }
    monkeypatch.setattr(tasks_mod, "SYSTEM_TASKS", [fake])
    monkeypatch.setattr("disk_cleaner.core.process.get_open_paths", lambda: set())
    out, _err = _capture(monkeypatch)
    assert cli.cli_main(["--snapshot", "create"]) == 0
    sid = out.getvalue().strip()
    assert sid.isdigit()
    out, _err = _capture(monkeypatch)
    assert cli.cli_main(["--snapshot", "list"]) == 0
    assert sid in out.getvalue()


def test_snapshot_diff_bad_args(xdg_env, monkeypatch):
    cli, _ = xdg_env
    _capture(monkeypatch)
    assert cli.cli_main(["--snapshot", "diff", "a", "b"]) == 2


# ---------- treemap export ----------


def test_export_treemap_creates_png(tmp_path, xdg_env, monkeypatch):
    cli, _ = xdg_env
    cairo = pytest.importorskip("cairo")  # noqa: F841 — runtime dep
    src = tmp_path / "treemap_src"
    src.mkdir()
    (src / "a.bin").write_bytes(b"x" * 4096)
    out_png = tmp_path / "tm.png"
    _capture(monkeypatch)
    rc = cli.cli_main(["--export-treemap", str(src), "-o", str(out_png)])
    assert rc == 0, f"rc={rc}"
    assert out_png.exists() and out_png.stat().st_size > 0


def test_export_treemap_requires_output(xdg_env, monkeypatch):
    cli, _ = xdg_env
    _capture(monkeypatch)
    assert cli.cli_main(["--export-treemap", "/tmp"]) == 2


# ---------- epilog ----------


def test_help_contains_examples(xdg_env, monkeypatch):
    cli, _ = xdg_env
    out, err = _capture(monkeypatch)
    with pytest.raises(SystemExit):
        cli.cli_main(["--help"])
    text = out.getvalue() + err.getvalue()
    assert "Examples:" in text
    assert "--scan" in text


# ---------- unified error helpers ----------


_ANSI_RE = __import__("re").compile(r"\x1b\[[0-9;]*[A-Za-z]")


def test_cmd_set_error_uses_unified_reporter(xdg_env, monkeypatch):
    """``_cmd_set`` reports schema errors via the unified ``error: ...`` prefix.

    Because tests replace stderr with a StringIO (non-TTY), the reporter
    falls back to plain text — assert the prefix is present and no ANSI
    escapes leak into a captured stream.
    """
    cli, _ = xdg_env
    _out, err = _capture(monkeypatch)
    rc = cli.cli_main(["--set", "bogus=1"])
    assert rc == 2
    text = err.getvalue()
    assert text.startswith("error: ") or "\nerror: " in "\n" + text
    assert "unknown key" in text
    assert not _ANSI_RE.search(text)


def test_cmd_snapshot_bad_subaction_uses_unified_reporter(xdg_env, monkeypatch):
    cli, _ = xdg_env
    _out, err = _capture(monkeypatch)
    rc = cli.cli_main(["--snapshot", "bogus"])
    assert rc == 2
    assert "error: " in err.getvalue()


def test_cmd_add_cleaner_invalid_json_uses_unified_reporter(tmp_path, xdg_env, monkeypatch):
    cli, _ = xdg_env
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    _out, err = _capture(monkeypatch)
    rc = cli.cli_main(["--add-cleaner", str(bad)])
    assert rc == 1
    assert "error: " in err.getvalue()
    assert "invalid JSON" in err.getvalue()


# ---------- enriched --watchdog-status ----------


def test_watchdog_status_stopped_shows_threshold_and_interval(xdg_env, monkeypatch):
    """When stopped, status still prints threshold + interval rows."""
    cli, _ = xdg_env
    out, _err = _capture(monkeypatch)
    rc = cli.cli_main(["--watchdog-status", "--no-color"])
    assert rc == 0
    text = out.getvalue()
    assert "STOPPED" in text
    assert "threshold" in text
    assert "interval" in text
    # No PID/uptime when stopped.
    assert "pid" not in text
    assert "uptime" not in text


def test_watchdog_status_running_shows_pid_and_uptime(xdg_env, monkeypatch):
    """Mock ``watchdog_running`` + a fake PID file: rendered output
    must include pid, uptime, threshold, interval."""
    cli, config = xdg_env
    # Drop a fake PID file under XDG_RUNTIME_DIR so _watchdog_pid_uptime
    # can read it. config.WATCHDOG_PID points there.
    from disk_cleaner.watchdog import daemon as dmn

    dmn.WATCHDOG_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    dmn.WATCHDOG_PID_FILE.write_text("12345")
    # Patch the cli's view of WATCHDOG_PID_FILE too (imported at top).
    monkeypatch.setattr(cli, "WATCHDOG_PID_FILE", dmn.WATCHDOG_PID_FILE)
    monkeypatch.setattr(cli, "watchdog_running", lambda: True)

    # Pre-seed a threshold so the row content is predictable.
    assert cli.cli_main(["--set", "watchdog.threshold=5G"]) == 0
    out, _err = _capture(monkeypatch)
    rc = cli.cli_main(["--watchdog-status", "--no-color"])
    assert rc == 0
    text = out.getvalue()
    assert "RUNNING" in text
    assert "12345" in text  # pid
    assert "uptime" in text
    assert "threshold" in text and "5G" in text
    assert "interval" in text


# ---------- enriched epilog ----------


def test_help_epilog_includes_new_examples(xdg_env, monkeypatch):
    cli, _ = xdg_env
    out, err = _capture(monkeypatch)
    with pytest.raises(SystemExit):
        cli.cli_main(["--help"])
    text = out.getvalue() + err.getvalue()
    # Script-mode (system + json)
    assert "--non-interactive --scan --sources system --format json" in text
    # Interactive cleanup (scan + clean)
    assert "--scan --clean" in text
    # Watchdog with threshold
    assert "watchdog.threshold=5G" in text


# ---------- confirm gate ----------


def test_clean_without_yes_aborts_on_non_tty(xdg_env, monkeypatch):
    """Without -y and with non-TTY stderr, confirm() returns default=False → abort."""
    cli, _ = xdg_env
    called = {"n": 0}

    def fake_clean():
        called["n"] += 1
        return 0, ""

    fake_task = {
        "name": "t",
        "path": "/x",
        "kind": "system",
        "size_bytes": 100,
        "size_human": "100 B",
        "score": 80,
        "reason": "ok",
        "risk": "low",
        "_task": {"name": "t", "clean_fn": fake_clean},
    }
    monkeypatch.setattr(cli, "cli_collect_tasks", lambda *a, **kw: [fake_task])
    _capture(monkeypatch)
    rc = cli.cli_main(["--clean", "--items", "t"])  # no -y, no TTY
    assert rc == 1
    assert called["n"] == 0
