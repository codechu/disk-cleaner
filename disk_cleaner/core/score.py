"""Smart suggestion scoring.

Converts a Task + size + kind + open-process information into a score
in the 0..100+ range and a one-line reason. Pure logic — UI-independent
and testable.
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Any

from ..i18n import _
from .process import path_holders

_RISK_FACTOR: dict[str, float] = {"low": 1.0, "medium": 0.6, "high": 0.15}
_KIND_BONUS: dict[str, int] = {
    "system": 10,  # usually safe, regenerated automatically
    "artifact": 8,
    "duplicate": 12,
    "oldfile": 5,
}


def _type_label(kind: str) -> str:
    """Translated label for a task ``kind`` (lazy so locale changes apply)."""
    return {
        "system": _("system cache"),
        "artifact": _("project artifact"),
        "duplicate": _("duplicate"),
        "oldfile": _("old file"),
    }.get(kind, "")


def compute_score_and_reason(
    task: dict[str, Any],
    size: int,
    kind: str,
    open_paths: set[tuple[str, str]],
) -> tuple[float, str]:
    """Compute a score (0-100+) and a one-line reason for a task."""
    path = task.get("path", "")
    risk = task.get("risk", "medium")
    desc = task.get("desc", "")

    reasons: list[str] = []
    score = 0.0

    # Size component: log scale (each 10× ≈ +30 points)
    size_gb = max(size, 1) / (1024**3)
    score += min(60, 30 * math.log10(max(size_gb, 0.001) + 1) + 30)

    score *= _RISK_FACTOR.get(risk, 0.5)
    score += _KIND_BONUS.get(kind, 0)

    # Age information (use mtime if available)
    age_days: float | None = None
    try:
        p = Path(os.path.expanduser(path))
        if p.exists():
            age_days = (time.time() - p.stat().st_mtime) / 86400
    except OSError:
        pass

    if age_days is not None and age_days > 30:
        score += min(20, age_days / 30 * 5)
        reasons.append(_("not touched in {n} days").format(n=int(age_days)))
    elif age_days is not None and age_days < 1:
        reasons.append(_("modified in last 24 hours"))
        score -= 30  # very recent — likely active

    # Process awareness
    holders = path_holders(path, open_paths)
    if holders:
        names = sorted(holders)[:3]
        reasons.append(_("currently open: {names}").format(names=", ".join(names)))
        score -= 40  # very risky

    # Risk text (active-project detection is already written into desc)
    if "ACTIVE" in desc or "AKTİF" in desc:
        reasons.append(_("active project, KEEP recommended"))
        score -= 60
    elif risk == "low":
        reasons.append(_("safe, regeneratable"))

    type_label = _type_label(kind)
    if type_label and not reasons:
        reasons.append(type_label)

    reason = " · ".join(reasons) if reasons else "—"
    return max(0, score), reason


__all__ = ["compute_score_and_reason"]
