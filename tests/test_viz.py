"""Viz katmanı — TreeNode, treemap layout, sunburst layout, hit_test, renkler."""
from __future__ import annotations

import math

from disk_cleaner.viz import (
    OTHER_MARKER,
    SunburstStrategy,
    TreemapStrategy,
    TreeNode,
    VizStrategy,
    build_tree,
    hit_test,
    is_hash_like,
    layout_sunburst,
    layout_treemap,
    node_color,
    sunburst_hit_test,
)


# ---------- helpers ----------


def _mk_tree(sizes: dict[str, int]) -> TreeNode:
    root = TreeNode("root", sum(sizes.values()), is_dir=True)
    root.children = [TreeNode(name, sz, is_dir=False) for name, sz in sizes.items()]
    return root


# ---------- TreeNode + build_tree ----------


def test_build_tree_simple(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 4096)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.bin").write_bytes(b"y" * 8192)
    tree = build_tree(tmp_path)
    assert tree is not None
    assert tree.is_dir
    assert tree.size > 0
    # Çocuklar boyuta göre azalan
    if len(tree.children) >= 2:
        for a, b in zip(tree.children, tree.children[1:]):
            assert a.size >= b.size


def test_build_tree_missing_returns_none(tmp_path):
    assert build_tree(tmp_path / "ghost") is None


# ---------- Treemap layout ----------


def test_layout_treemap_sets_rects():
    root = _mk_tree({"a": 600, "b": 300, "c": 100})
    layout_treemap(root, 0, 0, 100, 100)
    assert root.rect == (0, 0, 100, 100)
    for child in root.children:
        if child.path.startswith(OTHER_MARKER):
            continue
        assert child.rect is not None
        assert len(child.rect) == 4


def test_layout_treemap_small_grouped_in_other():
    # Bir sürü küçük + bir büyük → küçükler tek 'Diğer'
    sizes = {f"x{i}": 1 for i in range(10)}
    sizes["big"] = 1000
    root = _mk_tree(sizes)
    layout_treemap(root, 0, 0, 200, 200)
    others = [c for c in root.children if c.path.startswith(OTHER_MARKER)]
    assert len(others) == 1


def test_treemap_hit_test_finds_child():
    root = _mk_tree({"a": 600, "b": 400})
    layout_treemap(root, 0, 0, 100, 100)
    # 'a' büyük, sol sütun
    a = root.children[0]
    cx = a.rect[0] + a.rect[2] / 2
    cy = a.rect[1] + a.rect[3] / 2
    assert hit_test(root, cx, cy) is a


def test_treemap_strategy_layout_and_hit():
    root = _mk_tree({"a": 600, "b": 400})
    strat = TreemapStrategy()
    assert isinstance(strat, VizStrategy)
    strat.layout(root, 100.0, 100.0)
    assert root.rect == (0.0, 0.0, 100.0, 100.0)
    hit = strat.hit_test(root, 5.0, 5.0)
    assert hit is not None


# ---------- Sunburst layout ----------


def test_layout_sunburst_sets_polar_rect():
    root = _mk_tree({"a": 500, "b": 300, "c": 200})
    layout_sunburst(root, cx=100, cy=100, r_inner=10, r_step=30, max_depth=2)
    assert root.rect is not None
    assert len(root.rect) == 7
    cx, cy, r_in, r_out, a0, a1, _top = root.rect
    assert (cx, cy) == (100, 100)
    assert r_out > r_in
    assert math.isclose(a1 - a0, 2 * math.pi, rel_tol=1e-6)


def test_sunburst_hit_test_center_is_root():
    root = _mk_tree({"a": 500, "b": 500})
    layout_sunburst(root, cx=100, cy=100, r_inner=10, r_step=30, max_depth=2)
    # Halka içine bir nokta seç (r_inner + 5)
    hit = sunburst_hit_test(root, 115, 100)
    assert hit is not None


def test_sunburst_strategy_layout_and_hit():
    root = _mk_tree({"a": 600, "b": 400})
    strat = SunburstStrategy()
    assert isinstance(strat, VizStrategy)
    strat.layout(root, 200.0, 200.0)
    assert root.rect is not None
    assert len(root.rect) == 7


# ---------- colors + text ----------


def test_node_color_returns_rgb():
    r, g, b = node_color(0, 0, dark=False)
    assert 0 <= r <= 1 and 0 <= g <= 1 and 0 <= b <= 1


def test_node_color_dark_is_dimmer():
    light = node_color(0, 0, dark=False)
    dark = node_color(0, 0, dark=True)
    # Dark mode genelde daha düşük lightness/sat
    assert sum(dark) <= sum(light)


def test_node_color_other_is_gray():
    r, g, b = node_color(0, 0, dark=False, is_other=True)
    assert r == g == b


def test_is_hash_like():
    assert is_hash_like("a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")
    assert not is_hash_like("regular-file-name.txt")
    assert not is_hash_like("short")


def test_viz_strategy_draw_raises_by_default():
    import pytest

    root = _mk_tree({"a": 100})
    strat = TreemapStrategy()
    strat.layout(root, 50, 50)
    with pytest.raises(NotImplementedError):
        strat.draw(None, root)
