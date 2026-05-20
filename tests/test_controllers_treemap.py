# SPDX-License-Identifier: GPL-3.0-or-later

"""TreemapController — headless state machine testleri."""

from __future__ import annotations

from disk_cleaner.controllers import TreemapController
from disk_cleaner.viz import TreeNode


def _mk_node(path: str, size: int, children=None, is_dir=False) -> TreeNode:
    return TreeNode(path, size, children=children, is_dir=is_dir)


def test_initial_state():
    c = TreemapController()
    assert c.current_node is None
    assert c.history == []
    assert c.can_go_up is False
    assert c.has_node is False
    assert c.busy is False


def test_observer_callbacks_default_noop():
    """Calls don't blow up even if no callbacks are assigned."""
    c = TreemapController()
    # _set_busy fires the internal callback
    c._set_busy(True)
    c._set_busy(False)


def test_drill_in_pushes_history():
    c = TreemapController()
    root = _mk_node("/", 1000, is_dir=True)
    a = _mk_node("/a", 600, is_dir=True)
    b = _mk_node("/b", 400, is_dir=True)
    root.children = [a, b]
    c.current_node = root
    c.drill_in(a)
    assert c.current_node is a
    assert c.history == [root]
    assert c.can_go_up is True


def test_drill_in_refuses_non_dir():
    c = TreemapController()
    root = _mk_node("/", 100, is_dir=True)
    f = _mk_node("/x", 50, is_dir=False)
    root.children = [f]
    c.current_node = root
    c.drill_in(f)
    assert c.current_node is root  # must not change


def test_drill_in_refuses_self():
    c = TreemapController()
    root = _mk_node("/", 100, is_dir=True)
    c.current_node = root
    c.drill_in(root)
    assert c.history == []  # cannot drill into self


def test_drill_up_pops_history():
    c = TreemapController()
    root = _mk_node("/", 1000, is_dir=True)
    a = _mk_node("/a", 600, is_dir=True)
    root.children = [a]
    c.current_node = root
    c.drill_in(a)
    c.drill_up()
    assert c.current_node is root
    assert c.history == []


def test_drill_up_noop_when_empty():
    c = TreemapController()
    c.drill_up()
    assert c.current_node is None  # didn't blow up


def test_drill_to_truncates_history():
    """Drill three levels; drill_to the middle → history truncates to that level."""
    c = TreemapController()
    a = _mk_node("/a", 1000, is_dir=True)
    b = _mk_node("/a/b", 500, is_dir=True)
    cc = _mk_node("/a/b/c", 200, is_dir=True)
    d = _mk_node("/a/b/c/d", 100, is_dir=True)
    a.children = [b]
    b.children = [cc]
    cc.children = [d]
    c.current_node = a
    c.drill_in(b)
    c.drill_in(cc)
    c.drill_in(d)
    assert c.history == [a, b, cc]
    c.drill_to(b)
    assert c.current_node is b
    assert c.history == [a]


def test_drill_to_path_string():
    c = TreemapController()
    a = _mk_node("/a", 1000, is_dir=True)
    b = _mk_node("/a/b", 500, is_dir=True)
    a.children = [b]
    c.current_node = a
    c.drill_in(b)
    assert c.drill_to_path("/a") is True
    assert c.current_node is a


def test_drill_to_path_missing_returns_false():
    c = TreemapController()
    a = _mk_node("/a", 100, is_dir=True)
    c.current_node = a
    assert c.drill_to_path("/nonexistent") is False


def test_observer_fires_on_drill():
    c = TreemapController()
    root = _mk_node("/", 100, is_dir=True)
    a = _mk_node("/a", 50, is_dir=True)
    root.children = [a]
    c.current_node = root

    seen: list[tuple[str, list[str]]] = []
    c.on_current_changed = lambda cur, hist: seen.append((cur.path, [h.path for h in hist]))
    c.drill_in(a)
    c.drill_up()
    assert seen == [
        ("/a", ["/"]),
        ("/", []),
    ]


def test_observer_busy_signal():
    c = TreemapController()
    seen: list[bool] = []
    c.on_busy_changed = lambda b: seen.append(b)
    c._set_busy(True)
    c._set_busy(False)
    assert seen == [True, False]


def test_set_viz_mode_emits_observer():
    c = TreemapController()
    seen: list[str] = []
    c.on_viz_mode_changed = lambda m: seen.append(m)
    c.viz_mode = "treemap"  # baseline
    c.set_viz_mode("sunburst")
    c.set_viz_mode("sunburst")  # same value, no-op
    c.set_viz_mode("treemap")
    assert seen == ["sunburst", "treemap"]


def test_hit_test_returns_none_when_no_node():
    c = TreemapController()
    assert c.hit_test(10, 10) is None
