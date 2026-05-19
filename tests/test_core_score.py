"""Tests for ``core.score.compute_score_and_reason``.

Covers the scoring/reason engine that drives smart-scan suggestions.
Pure logic: no I/O, no GUI. High-leverage test surface.
"""

from __future__ import annotations

from disk_cleaner.core.score import compute_score_and_reason

KB = 1024
MB = 1024**2
GB = 1024**3


def _task(path: str = "/nonexistent/path/123", risk: str = "low", desc: str = "") -> dict:
    return {"path": path, "risk": risk, "desc": desc}


# ── Size component ───────────────────────────────────────────────────


def test_score_increases_with_size():
    s_small, _ = compute_score_and_reason(_task(), 10 * MB, "system", set())
    s_large, _ = compute_score_and_reason(_task(), 10 * GB, "system", set())
    assert s_large > s_small


def test_score_zero_size_does_not_crash():
    score, _ = compute_score_and_reason(_task(), 0, "system", set())
    assert score >= 0


# ── Risk multiplier ──────────────────────────────────────────────────


def test_high_risk_scores_lower_than_low_risk():
    s_low, _ = compute_score_and_reason(_task(risk="low"), 1 * GB, "system", set())
    s_high, _ = compute_score_and_reason(_task(risk="high"), 1 * GB, "system", set())
    assert s_low > s_high


def test_medium_risk_between_low_and_high():
    s_low, _ = compute_score_and_reason(_task(risk="low"), 1 * GB, "system", set())
    s_med, _ = compute_score_and_reason(_task(risk="medium"), 1 * GB, "system", set())
    s_high, _ = compute_score_and_reason(_task(risk="high"), 1 * GB, "system", set())
    assert s_low >= s_med >= s_high


def test_unknown_risk_defaults_to_0_5_factor():
    """Unknown risk uses 0.5 multiplier — should be between low and high."""
    s_unknown, _ = compute_score_and_reason(_task(risk="unknown"), 1 * GB, "system", set())
    s_low, _ = compute_score_and_reason(_task(risk="low"), 1 * GB, "system", set())
    s_high, _ = compute_score_and_reason(_task(risk="high"), 1 * GB, "system", set())
    assert s_high < s_unknown < s_low


# ── Kind bonus ───────────────────────────────────────────────────────


def test_duplicate_kind_bonus_higher_than_oldfile():
    s_dup, _ = compute_score_and_reason(_task(), 1 * GB, "duplicate", set())
    s_old, _ = compute_score_and_reason(_task(), 1 * GB, "oldfile", set())
    assert s_dup > s_old


def test_unknown_kind_no_bonus():
    s_known, _ = compute_score_and_reason(_task(), 1 * GB, "system", set())
    s_unknown, _ = compute_score_and_reason(_task(), 1 * GB, "weird", set())
    assert s_known > s_unknown


# ── Open paths (process awareness) ───────────────────────────────────


def test_open_path_drops_score_significantly():
    open_paths = {("/tmp/cache.bin", "chrome")}
    s_open, reason_open = compute_score_and_reason(
        _task(path="/tmp/cache.bin"),
        1 * GB,
        "system",
        open_paths,
    )
    s_closed, _ = compute_score_and_reason(
        _task(path="/tmp/cache.bin"),
        1 * GB,
        "system",
        set(),
    )
    assert s_open < s_closed - 30  # process awareness penalty kicks in


def test_open_path_reason_mentions_process():
    open_paths = {("/tmp/holdme", "firefox")}
    _score, reason = compute_score_and_reason(
        _task(path="/tmp/holdme"),
        100 * MB,
        "system",
        open_paths,
    )
    assert "firefox" in reason


# ── Active project marker ────────────────────────────────────────────


def test_active_marker_drops_score_heavily():
    # Use larger size so base score is high enough that 60-point penalty
    # produces a visible delta (without hitting the 0 floor).
    base_score, _ = compute_score_and_reason(_task(risk="low"), 100 * GB, "artifact", set())
    active_score, reason = compute_score_and_reason(
        _task(risk="low", desc="ACTIVE project (last commit 2 days ago)"),
        100 * GB,
        "artifact",
        set(),
    )
    assert active_score < base_score
    # Reason mentions keep
    assert "KEEP" in reason.upper() or "active" in reason.lower()


def test_legacy_turkish_marker_still_works():
    """Backward-compat: data with old 'AKTİF' marker still suppresses score."""
    _, reason = compute_score_and_reason(
        _task(desc="AKTİF proje"),
        1 * GB,
        "artifact",
        set(),
    )
    # Should produce a "keep" reason regardless of which marker was used
    assert "KEEP" in reason.upper() or "active" in reason.lower()


# ── Reason structure ─────────────────────────────────────────────────


def test_safe_low_risk_returns_safe_reason():
    _score, reason = compute_score_and_reason(_task(risk="low"), 100 * MB, "system", set())
    assert "safe" in reason.lower() or "regenerat" in reason.lower()


def test_high_risk_does_not_get_safe_marker():
    _score, reason = compute_score_and_reason(_task(risk="high"), 100 * MB, "system", set())
    assert "safe" not in reason.lower()


def test_reason_never_empty():
    """Every score result must include a reason — even if just kind label."""
    for kind in ("system", "artifact", "duplicate", "oldfile"):
        _s, reason = compute_score_and_reason(_task(), 100 * MB, kind, set())
        assert reason != ""
        assert reason != "—" or kind == "weird"


# ── Score bounds ─────────────────────────────────────────────────────


def test_score_never_negative():
    """Even with all penalties, score floor is 0."""
    open_paths = {("/path", "browser")}
    s, _ = compute_score_and_reason(
        _task(path="/path", risk="high", desc="ACTIVE"),
        1 * MB,
        "weird",
        open_paths,
    )
    assert s >= 0
