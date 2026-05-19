"""TaskListController — headless state machine testleri."""
from __future__ import annotations

import threading
import time

from disk_cleaner.controllers import (
    CleanPreview,
    PreviewResult,
    TaskListController,
)


def _mk_task(name: str, size: int, risk: str = "low", desc: str = "") -> dict:
    """Synthetic task dict — with real size_fn/clean_fn."""
    return {
        "name": name,
        "desc": desc or f"{name} description",
        "risk": risk,
        "path": f"/fake/{name}",
        "size_fn": lambda s=size: s,
        "clean_fn": lambda: (0, f"{name} cleaned"),
    }


def _wait_until(predicate, timeout=2.0):
    """Poll until the scan finishes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_initial_state():
    c = TaskListController(lambda: [])
    assert c.busy is False
    assert c.rows == []
    assert c.total_bytes == 0
    assert c.selected_count == 0


def test_scan_populates_rows():
    tasks = [
        _mk_task("a", 200 * 1024 * 1024),
        _mk_task("b", 50 * 1024 * 1024),
    ]
    c = TaskListController(lambda: tasks)
    c.start_scan()
    assert _wait_until(lambda: not c.busy and len(c.rows) == 2)
    assert c.rows[0].name == "a"
    assert c.rows[0].size_bytes == 200 * 1024 * 1024
    assert c.rows[1].size_bytes == 50 * 1024 * 1024


def test_auto_select_low_risk_above_threshold():
    """Low risk + >100MB is auto-selected."""
    tasks = [
        _mk_task("big", 200 * 1024 * 1024, risk="low"),
        _mk_task("small", 50 * 1024 * 1024, risk="low"),
        _mk_task("big_high", 500 * 1024 * 1024, risk="high"),
    ]
    c = TaskListController(lambda: tasks, auto_select=True)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    assert c.rows[0].checked is True   # big low risk → auto
    assert c.rows[1].checked is False  # small (<100MB)
    assert c.rows[2].checked is False  # high risk


def test_auto_select_disabled():
    tasks = [_mk_task("big", 200 * 1024 * 1024, risk="low")]
    c = TaskListController(lambda: tasks, auto_select=False)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    assert c.rows[0].checked is False


def test_toggle_emits_observers():
    tasks = [_mk_task("a", 1000)]
    c = TaskListController(lambda: tasks, auto_select=False)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    seen_total: list[tuple[int, int]] = []
    c.on_total_changed = lambda count, bts: seen_total.append((count, bts))
    c.toggle(0)
    assert c.rows[0].checked is True
    assert seen_total[-1] == (1, 1000)
    c.toggle(0)
    assert c.rows[0].checked is False
    assert seen_total[-1] == (0, 0)


def test_select_all_none():
    tasks = [_mk_task("a", 100), _mk_task("b", 200), _mk_task("c", 300)]
    c = TaskListController(lambda: tasks, auto_select=False)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    c.select_all()
    assert c.selected_count == 3
    assert c.total_bytes == 600
    c.select_none()
    assert c.selected_count == 0
    assert c.total_bytes == 0


def test_start_clean_requires_selection():
    c = TaskListController(lambda: [])
    started = c.start_clean(confirm=lambda _: True)
    assert started is False


def test_start_clean_confirm_rejected():
    tasks = [_mk_task("a", 100)]
    c = TaskListController(lambda: tasks, auto_select=False)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    c.toggle(0)
    started = c.start_clean(confirm=lambda _: False)
    assert started is False


def test_start_clean_executes():
    cleaned = []
    task = _mk_task("a", 100)
    task["clean_fn"] = lambda: (cleaned.append("done"), (0, "ok"))[1]
    c = TaskListController(lambda: [task], auto_select=False)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    c.toggle(0)
    started = c.start_clean(confirm=lambda _: True)
    assert started is True
    assert _wait_until(lambda: not c.busy)
    assert cleaned == ["done"]


def test_clean_preview_data():
    tasks = [_mk_task(f"t{i}", 100 * i) for i in range(1, 4)]
    c = TaskListController(lambda: tasks, auto_select=False)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    c.select_all()
    captured: list[CleanPreview] = []
    def confirm(p):
        captured.append(p)
        return False
    c.start_clean(confirm)
    assert len(captured) == 1
    assert captured[0].count == 3
    assert captured[0].total_bytes == 100 + 200 + 300
    assert len(captured[0].items) == 3


def test_provider_signature_fallback():
    """Providers may have different signatures."""
    # provider takes only ()
    c = TaskListController(lambda: [_mk_task("a", 100)])
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    assert len(c.rows) == 1

    # provider takes (cancel)
    c2 = TaskListController(lambda cancel: [_mk_task("b", 200)])
    c2.start_scan()
    assert _wait_until(lambda: not c2.busy)
    assert c2.rows[0].name == "b"


def test_preview_request_missing_path(tmp_path):
    tasks = [{
        "name": "ghost",
        "desc": "",
        "risk": "low",
        "path": str(tmp_path / "does-not-exist"),
        "size_fn": lambda: 0,
        "clean_fn": lambda: (0, ""),
    }]
    c = TaskListController(lambda: tasks, auto_select=False)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    captured: list[PreviewResult] = []
    c.on_preview = lambda r: captured.append(r)
    c.request_preview(0)
    assert _wait_until(lambda: any(p.state == "missing" for p in captured))


def test_preview_directory(tmp_path):
    (tmp_path / "a.txt").write_text("hi")
    (tmp_path / "b.txt").write_text("bye")
    tasks = [{
        "name": "dir",
        "desc": "",
        "risk": "low",
        "path": str(tmp_path),
        "size_fn": lambda: 0,
        "clean_fn": lambda: (0, ""),
    }]
    c = TaskListController(lambda: tasks, auto_select=False)
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    captured: list[PreviewResult] = []
    c.on_preview = lambda r: captured.append(r)
    c.request_preview(0)
    assert _wait_until(
        lambda: any(p.state == "directory" for p in captured), timeout=3
    )
    dir_result = next(p for p in captured if p.state == "directory")
    assert dir_result.total_items == 2


def test_cancel_stops_scan():
    """Slow provider + cancel → the operation stops."""
    started_flag = threading.Event()

    def slow_provider(cancel=None):
        started_flag.set()
        # Wait for cancel
        if cancel is not None:
            cancel.wait(timeout=2)
        return [_mk_task("a", 100)]

    c = TaskListController(slow_provider)
    c.start_scan()
    assert started_flag.wait(timeout=1)
    c.cancel()
    assert _wait_until(lambda: not c.busy, timeout=3)


def test_observer_busy_state():
    seen: list[tuple[bool, str]] = []
    c = TaskListController(lambda: [_mk_task("a", 100)])
    c.on_busy_changed = lambda b, p: seen.append((b, p))
    c.start_scan()
    assert _wait_until(lambda: not c.busy)
    assert seen[0][0] is True       # first: busy=True
    assert seen[-1][0] is False     # last: busy=False
