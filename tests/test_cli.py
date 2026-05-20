"""Subprocess-based CLI regression tests.

Covered bugs:
- ``--watchdog-status`` / ``--watchdog-stop`` returned exit 1 when the
  daemon wasn't running. STOPPED is a normal observable state — both
  should now exit 0.
- ``--scan > file.json`` raised ``OSError: Bad file descriptor`` for a
  prior agent. Regression test runs the scan with stdout/stderr both
  redirected to files and verifies clean exit + nonzero output.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _env_with_tmp_xdg(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    env["XDG_RUNTIME_DIR"] = str(tmp_path / "runtime")
    env["DISK_CLEANER_LANG"] = "en"
    # Ensure no stray watchdog from a prior run leaks in.
    for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
        Path(env[k]).mkdir(parents=True, exist_ok=True)
    return env


def test_watchdog_status_stopped_exits_zero(tmp_path):
    env = _env_with_tmp_xdg(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "disk_cleaner", "--watchdog-status"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    assert r.returncode == 0, (
        f"--watchdog-status STOPPED should be exit 0, got {r.returncode}\n"
        f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    )
    assert "STOPPED" in r.stdout or "stopped" in r.stdout.lower()


def test_watchdog_stop_when_not_running_exits_zero(tmp_path):
    env = _env_with_tmp_xdg(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "disk_cleaner", "--watchdog-stop"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    assert r.returncode == 0, (
        f"--watchdog-stop when not running should be exit 0, got {r.returncode}\n"
        f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    )


def test_scan_redirected_to_file_does_not_crash(tmp_path):
    """``--scan > file.json 2> file.err`` must exit 0 with non-empty output.

    A prior agent's session reported ``OSError: Bad file descriptor`` here.
    We exercise the same shape via explicit stdout/stderr file redirection.
    """
    env = _env_with_tmp_xdg(tmp_path)
    out_file = tmp_path / "scan.json"
    err_file = tmp_path / "scan.err"
    with open(out_file, "wb") as out_fp, open(err_file, "wb") as err_fp:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "disk_cleaner",
                "--scan",
                "--sources",
                "system",
                "--format",
                "json",
            ],
            stdout=out_fp,
            stderr=err_fp,
            env=env,
            cwd=str(REPO_ROOT),
            timeout=120,
        )
    if r.returncode != 0:
        # surface error contents for debugging
        pytest.fail(
            f"--scan redirected to file exited {r.returncode}\n"
            f"stderr file contents:\n{err_file.read_text(errors='replace')}"
        )
    assert out_file.stat().st_size > 0, "stdout redirect produced empty file"
    # Must be valid JSON
    import json

    data = json.loads(out_file.read_text())
    assert "items" in data and "totals" in data


# ---------- script-mode flags ----------


_ANSI_RE = __import__("re").compile(r"\x1b\[[0-9;]*[A-Za-z]")


def test_non_interactive_scan_json(tmp_path):
    """--non-interactive implies --format=json + no color + no progress."""
    env = _env_with_tmp_xdg(tmp_path)
    r = subprocess.run(
        [
            sys.executable, "-m", "disk_cleaner",
            "--non-interactive", "--scan", "--sources", "system",
        ],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
    )
    assert r.returncode == 0, f"stderr={r.stderr!r}"
    # Default format must be json under --non-interactive.
    import json as _json
    data = _json.loads(r.stdout)
    assert "items" in data and "totals" in data
    # No ANSI anywhere.
    assert not _ANSI_RE.search(r.stdout)
    assert not _ANSI_RE.search(r.stderr)


def test_no_color_strips_ansi(tmp_path):
    """--no-color produces ANSI-free output even when format=table is forced."""
    env = _env_with_tmp_xdg(tmp_path)
    # Force a TTY-style format explicitly; stdout is a pipe here so colors
    # would already be off — but --no-color must work in *both* cases.
    r = subprocess.run(
        [
            sys.executable, "-m", "disk_cleaner",
            "--scan", "--sources", "system", "--format", "table", "--no-color",
        ],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
    )
    assert r.returncode == 0
    assert not _ANSI_RE.search(r.stdout)
    assert not _ANSI_RE.search(r.stderr)


def test_no_progress_no_progress_line(tmp_path):
    """--no-progress suppresses the per-task progress redraw on stderr."""
    env = _env_with_tmp_xdg(tmp_path)
    r = subprocess.run(
        [
            sys.executable, "-m", "disk_cleaner",
            "--scan", "--sources", "system", "--format", "json", "--no-progress",
        ],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
    )
    assert r.returncode == 0
    # ProgressLine uses CR ("\r") for redraws; with --no-progress stderr
    # should not contain that.
    assert "\r" not in r.stderr


def test_non_interactive_clean_without_items_or_sources_refused(tmp_path):
    """Safety: --non-interactive --clean with no constraints must refuse."""
    env = _env_with_tmp_xdg(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "disk_cleaner", "--non-interactive", "--clean"],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
    )
    assert r.returncode == 2, f"expected exit 2, got {r.returncode}; stderr={r.stderr!r}"
    assert "items" in r.stderr.lower() or "sources" in r.stderr.lower()
