"""MainController — headless state machine testleri."""

from __future__ import annotations

import pytest

from disk_cleaner import runtime
from disk_cleaner.controllers import DiskUsage, MainController, Mount
from disk_cleaner.controllers.main import (
    _COLOR_GREEN,
    _COLOR_RED,
    _COLOR_YELLOW,
    read_disk_usage,
)


def test_disk_usage_label_markup():
    u = DiskUsage(total="468G", used="338G", avail="105G", percent=77, color=_COLOR_YELLOW)
    markup = u.label_markup
    assert "77% full" in markup
    assert "#bf8700" in markup
    assert "338G / 468G" in markup


def test_read_disk_usage_root():
    """Real df call — must produce a result for /."""
    u = read_disk_usage("/")
    assert u is not None
    assert 0 <= u.percent <= 100
    # Color thresholds are consistent
    if u.percent >= 90:
        assert u.color == _COLOR_RED
    elif u.percent >= 75:
        assert u.color == _COLOR_YELLOW
    else:
        assert u.color == _COLOR_GREEN


def test_read_disk_usage_invalid_returns_none():
    u = read_disk_usage("/nonexistent-mount-xyz")
    assert u is None


def test_controller_initial_state():
    c = MainController()
    assert len(c.mounts) >= 1
    assert c.current_mount in [m.target for m in c.mounts]


def test_controller_fs_warning_for_unknown_mount():
    c = MainController()
    assert c.fs_warning_for("/nonexistent") is None


def test_controller_find_mount():
    c = MainController()
    m = c.find_mount(c.current_mount)
    assert m is not None
    assert m.target == c.current_mount


def test_set_mount_emits_observer():
    c = MainController()
    if len(c.mounts) < 2:
        pytest.skip("no second mount")
    other = next(m.target for m in c.mounts if m.target != c.current_mount)
    seen: list[str] = []
    c.on_mount_changed = lambda t: seen.append(t)
    c.set_mount(other)
    assert seen == [other]
    assert c.current_mount == other


def test_set_mount_same_target_noop():
    c = MainController()
    seen: list[str] = []
    c.on_mount_changed = lambda t: seen.append(t)
    c.set_mount(c.current_mount)
    assert seen == []


def test_set_trash_mode_updates_runtime():
    c = MainController()
    seen: list[bool] = []
    c.on_trash_mode_changed = lambda v: seen.append(v)
    c.on_log = lambda _msg: None
    # Toggle
    original = runtime.TRASH_MODE
    c.set_trash_mode(not original)
    assert runtime.TRASH_MODE == (not original)
    assert seen == [not original]
    # Restore
    c.set_trash_mode(original)


def test_set_dry_run_updates_runtime():
    c = MainController()
    seen: list[bool] = []
    c.on_dry_run_changed = lambda v: seen.append(v)
    c.on_log = lambda _msg: None
    original = runtime.DRY_RUN
    c.set_dry_run(not original)
    assert runtime.DRY_RUN == (not original)
    assert seen == [not original]
    c.set_dry_run(original)


def test_btrfs_fs_warning_text():
    """fs_warning_for emits help text for a synthetic BTRFS mount."""
    c = MainController()
    # Inject fake mount
    c.mounts = [
        Mount(
            target="/btrfs",
            source="/dev/x",
            fstype="btrfs",
            size="1T",
            used="0",
            avail="1T",
            pcent="0",
        )
    ]
    msg = c.fs_warning_for("/btrfs")
    assert msg is not None
    assert "btrfs" in msg.lower()
    assert "btdu" in msg


def test_zfs_fs_warning_text():
    c = MainController()
    c.mounts = [
        Mount(
            target="/zfs",
            source="zpool/x",
            fstype="zfs",
            size="1T",
            used="0",
            avail="1T",
            pcent="0",
        )
    ]
    msg = c.fs_warning_for("/zfs")
    assert msg is not None
    assert "zfs" in msg.lower()
    assert "snapshot" in msg


def test_no_fs_warning_for_ext4():
    c = MainController()
    c.mounts = [
        Mount(
            target="/ext4",
            source="/dev/x",
            fstype="ext4",
            size="1T",
            used="0",
            avail="1T",
            pcent="0",
        )
    ]
    assert c.fs_warning_for("/ext4") is None


def test_save_panel_entries():
    """Writing to settings.json — must not raise TypeError."""
    c = MainController()
    c.save_panel_entries({"artifacts": "/foo", "explorer": "/bar"})
    from disk_cleaner.settings import SETTINGS

    assert SETTINGS.get("entries", {}).get("artifacts") == "/foo"


def test_refresh_disk_usage_emits():
    c = MainController()
    seen: list[DiskUsage | None] = []
    c.on_disk_usage_updated = lambda u: seen.append(u)
    c.refresh_disk_usage()
    assert len(seen) == 1
    # Active mount is valid; the result must not be None
    if c.current_mount == "/":
        assert seen[0] is not None
