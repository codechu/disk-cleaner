"""SuggestionController — headless state machine testleri."""

from __future__ import annotations

from disk_cleaner.controllers import (
    SuggestionController,
    SuggestionRow,
)
from disk_cleaner.controllers.suggestion import (
    _LOW_COLOR,
    _compute_auto_select,
    _group_enriched,
)


def _t(name: str, size: int = 100, risk: str = "low", desc: str = "") -> dict:
    return {
        "name": name,
        "desc": desc or f"{name} description",
        "risk": risk,
        "path": f"/fake/{name}",
        "size_fn": lambda s=size: s,
        "clean_fn": lambda: (0, "ok"),
    }


def test_group_enriched_artifact_grouping():
    """Two or more artifacts of the same type form a group; lone ones stay single."""
    enriched = [
        (_t("a"), 100, "artifact", 80, ""),
        (_t("b"), 100, "artifact", 70, ""),
        (_t("c"), 100, "system", 60, ""),
    ]
    enriched[0][0]["path"] = "/x/node_modules"
    enriched[1][0]["path"] = "/y/node_modules"
    groups, singles = _group_enriched(enriched)
    assert "📦 node_modules" in groups
    assert len(groups["📦 node_modules"]) == 2
    assert len(singles) == 1
    assert singles[0][2] == "system"


def test_group_enriched_single_artifact_unpacks():
    """A single-item artifact group is unfolded and falls into singles."""
    t = _t("lonely", 100, "low")
    t["path"] = "/x/lonely_thing"
    enriched = [(t, 100, "artifact", 50, "")]
    groups, singles = _group_enriched(enriched)
    assert groups == {}
    assert len(singles) == 1


def test_auto_select_top_n():
    """Top 5 low-risk + score>=60 + 5GB cap."""
    enriched = []
    for i in range(10):
        t = _t(f"big{i}", 200 * 1024 * 1024, "low")
        enriched.append((t, 200 * 1024 * 1024, "system", 90 - i, ""))
    groups, singles = _group_enriched(enriched)
    auto = _compute_auto_select(groups, singles)
    assert len(auto) == 5  # AUTO_SELECT_TOP_N


def test_auto_select_skips_high_risk():
    enriched = [
        (_t("a", risk="high"), 200 * 1024 * 1024, "system", 90, ""),
        (_t("b", risk="low"), 200 * 1024 * 1024, "system", 80, ""),
    ]
    groups, singles = _group_enriched(enriched)
    auto = _compute_auto_select(groups, singles)
    assert len(auto) == 1
    # Only b (low) is selected
    selected_names = [t.get("name") for t, _, _, _, _ in singles if id(t) in auto]
    assert selected_names == ["b"]


def test_auto_select_skips_active_project():
    enriched = [
        (
            _t("a", desc="⚠ ACTIVE project (last git commit 3 days ago)"),
            200 * 1024 * 1024,
            "artifact",
            90,
            "",
        ),
        (_t("b"), 200 * 1024 * 1024, "system", 80, ""),
    ]
    groups, singles = _group_enriched(enriched)
    auto = _compute_auto_select(groups, singles)
    assert len(auto) == 1
    assert _t_in(auto, "b", singles)


def test_auto_select_skips_open_paths():
    enriched = [
        (_t("a"), 200 * 1024 * 1024, "system", 90, "currently open: chrome"),
        (_t("b"), 200 * 1024 * 1024, "system", 80, ""),
    ]
    groups, singles = _group_enriched(enriched)
    auto = _compute_auto_select(groups, singles)
    assert len(auto) == 1


def test_auto_select_cumulative_cap():
    """5GB cap — must stop once the cumulative total would exceed it."""
    # Her biri 1.5 GB, 5 tane = 7.5 GB, ama cap 5 GB
    one_gb_half = int(1.5 * 1024 * 1024 * 1024)
    enriched = [(_t(f"t{i}"), one_gb_half, "system", 90 - i, "") for i in range(5)]
    groups, singles = _group_enriched(enriched)
    auto = _compute_auto_select(groups, singles)
    # 3 items (4.5 GB) should be selected; the 4th overflows
    assert len(auto) == 3


def test_controller_select_all_none():
    c = SuggestionController()
    c.rows = [
        SuggestionRow(
            tid=-1,
            name="grp",
            score=10,
            size_bytes=0,
            size_text="0 B",
            reason="",
            risk_color=_LOW_COLOR,
            kind="group",
            is_group=True,
            children=[
                SuggestionRow(
                    tid=0,
                    name="c1",
                    score=10,
                    size_bytes=100,
                    size_text="100 B",
                    reason="",
                    risk_color=_LOW_COLOR,
                    kind="system",
                    is_group=False,
                ),
                SuggestionRow(
                    tid=1,
                    name="c2",
                    score=20,
                    size_bytes=200,
                    size_text="200 B",
                    reason="",
                    risk_color=_LOW_COLOR,
                    kind="system",
                    is_group=False,
                ),
            ],
        ),
        SuggestionRow(
            tid=2,
            name="s",
            score=30,
            size_bytes=300,
            size_text="300 B",
            reason="",
            risk_color=_LOW_COLOR,
            kind="system",
            is_group=False,
        ),
    ]
    c.tasks = {0: _t("c1", 100), 1: _t("c2", 200), 2: _t("s", 300)}
    c.select_all()
    assert c.selected_count == 3
    assert c.total_bytes == 600
    c.select_none()
    assert c.selected_count == 0


def test_controller_toggle_group_propagates_to_children():
    c = SuggestionController()
    c.rows = [
        SuggestionRow(
            tid=-1,
            name="grp",
            score=10,
            size_bytes=300,
            size_text="300 B",
            reason="",
            risk_color=_LOW_COLOR,
            kind="group",
            is_group=True,
            children=[
                SuggestionRow(
                    tid=0,
                    name="c1",
                    score=10,
                    size_bytes=100,
                    size_text="",
                    reason="",
                    risk_color=_LOW_COLOR,
                    kind="system",
                    is_group=False,
                ),
                SuggestionRow(
                    tid=1,
                    name="c2",
                    score=20,
                    size_bytes=200,
                    size_text="",
                    reason="",
                    risk_color=_LOW_COLOR,
                    kind="system",
                    is_group=False,
                ),
            ],
        ),
    ]
    c.tasks = {0: _t("c1", 100), 1: _t("c2", 200)}
    c.toggle(0, None)  # toggle the group
    assert c.rows[0].checked is True
    assert c.rows[0].children[0].checked is True
    assert c.rows[0].children[1].checked is True
    assert c.selected_count == 2


def test_select_target_picks_by_score():
    c = SuggestionController()
    c.rows = [
        SuggestionRow(
            tid=i,
            name=f"t{i}",
            score=score,
            size_bytes=size,
            size_text="",
            reason="",
            risk_color=_LOW_COLOR,
            kind="system",
            is_group=False,
        )
        for i, (score, size) in enumerate(
            [
                (90, 200 * 1024 * 1024),  # 200 MB
                (80, 300 * 1024 * 1024),  # 300 MB
                (70, 100 * 1024 * 1024),  # 100 MB
                (60, 500 * 1024 * 1024),  # 500 MB
            ]
        )
    ]
    c.tasks = {i: _t(f"t{i}", 0) for i in range(4)}
    picked = c.select_target(500 * 1024 * 1024)
    # 200 + 300 = 500MB, or at least reach 500MB
    # Highest scores are 90 (200MB), 80 (300MB) — cumulative 500MB
    assert picked >= 2


def test_export_rows():
    c = SuggestionController()
    c.rows = [
        SuggestionRow(
            tid=0,
            name="a",
            score=10,
            size_bytes=100,
            size_text="100 B",
            reason="r1",
            risk_color=_LOW_COLOR,
            kind="system",
            is_group=False,
            checked=True,
        ),
    ]
    c.tasks = {0: _t("a", 100, risk="low")}
    rows = c.export_rows()
    assert len(rows) == 1
    assert rows[0].name == "a"
    assert rows[0].path == "/fake/a"
    assert rows[0].selected is True
    assert rows[0].risk == "low"


def _t_in(auto_set, name, singles):
    for t, _, _, _, _ in singles:
        if id(t) in auto_set and t.get("name") == name:
            return True
    return False
