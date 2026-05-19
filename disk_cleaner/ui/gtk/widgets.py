"""UI paylaşımlı yardımcılar — sabitler, küçük helper'lar.

``RISK_COLORS`` paneller arası tutarlı risk göstergesi (renk + etiket).
"""
from __future__ import annotations

from ...i18n import _

RISK_COLORS: dict[str, tuple[str, str]] = {
    "low": ("#1a7f37", _("🟢 Low")),
    "medium": ("#bf8700", _("🟡 Medium")),
    "high": ("#cf222e", _("🔴 High")),
}

__all__ = ["RISK_COLORS"]
