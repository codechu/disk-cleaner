"""Regression tests for packaging/disk-cleaner.desktop.

Bug: GNOME shell shows a generic icon for Disk Cleaner because the
desktop entry is missing ``StartupWMClass`` — without it, shell cannot
match the running window back to this file.
"""

from __future__ import annotations

import configparser
import shutil
import subprocess
from pathlib import Path

import pytest

DESKTOP_FILE = Path(__file__).resolve().parents[1] / "packaging" / "disk-cleaner.desktop"
EXPECTED_WMCLASS = "codechu-disk-cleaner"


def _read_entry() -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.read(DESKTOP_FILE, encoding="utf-8")
    return cp


def test_desktop_file_exists() -> None:
    assert DESKTOP_FILE.is_file(), f"missing {DESKTOP_FILE}"


def test_startup_wm_class_present_and_matches_snap_app() -> None:
    cp = _read_entry()
    assert cp.has_section("Desktop Entry")
    assert cp.has_option("Desktop Entry", "StartupWMClass"), (
        "Desktop entry must declare StartupWMClass so GNOME shell can "
        "match the running window to the .desktop file."
    )
    assert cp.get("Desktop Entry", "StartupWMClass") == EXPECTED_WMCLASS


def test_required_keys_present() -> None:
    cp = _read_entry()
    for key in ("Type", "Name", "Exec", "Icon"):
        assert cp.has_option("Desktop Entry", key), f"missing {key}"
    assert cp.get("Desktop Entry", "Type") == "Application"


def test_desktop_file_validate() -> None:
    if not shutil.which("desktop-file-validate"):
        pytest.skip("desktop-file-validate not available")
    result = subprocess.run(
        ["desktop-file-validate", str(DESKTOP_FILE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"desktop-file-validate failed:\n{result.stdout}\n{result.stderr}"
    )
