"""Shared UI helpers — constants and small helpers.

``RISK_COLORS`` gives a consistent risk indicator (color + label)
across panels.
"""
from __future__ import annotations

from ...i18n import _

RISK_COLORS: dict[str, tuple[str, str]] = {
    "low": ("#1a7f37", _("🟢 Low")),
    "medium": ("#bf8700", _("🟡 Medium")),
    "high": ("#cf222e", _("🔴 High")),
}

__all__ = ["RISK_COLORS"]
