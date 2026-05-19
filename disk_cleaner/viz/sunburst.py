"""Sunburst (radial treemap) layout + hit-test.

Her halka bir derinlik. Çok küçük dilimler tek bir 'Diğer' yumağına
toplanır; bu yumak parent'ın %15'inden küçükse gösterilmez (boş bırakılır).
"""
from __future__ import annotations

import math
from typing import Optional

from ..i18n import _
from .strategy import VizStrategy
from .tree_node import TreeNode
from .treemap import OTHER_MARKER

_DEFAULT_MAX_DEPTH = 3
_DEFAULT_MIN_ARC = 0.06
_OTHER_VISIBLE_FRAC = 0.15


def layout_sunburst(
    node: TreeNode,
    cx: float,
    cy: float,
    r_inner: float,
    r_step: float,
    max_depth: int = _DEFAULT_MAX_DEPTH,
    start_angle: float = -math.pi / 2,
    end_angle: float = 3 * math.pi / 2,
    depth: int = 0,
    top_idx: int = 0,
    min_arc: float = _DEFAULT_MIN_ARC,
) -> None:
    """Sunburst halka yerleşimi — ``node.rect``'i 7-tuple yapar.

    ``rect = (cx, cy, r_in, r_out, a0, a1, top_idx)``. Küçük dilimler tek
    bir 'Diğer' yumağında toplanır; eşik altında ise yumak gösterilmez.
    """
    node.rect = (cx, cy, r_inner, r_inner + r_step, start_angle, end_angle, top_idx)
    # Önceki render'lardan kalan virtual 'Diğer' yumaklarını temizle.
    node.children = [c for c in node.children if not c.path.startswith(OTHER_MARKER)]
    if depth >= max_depth or not node.children or node.size == 0:
        return
    children = sorted(node.children, key=lambda c: -c.size)
    total = sum(c.size for c in children) or 1
    total_arc = end_angle - start_angle
    rendered: list[tuple[TreeNode, float]] = []
    skipped_size = 0
    skipped_count = 0
    for c in children:
        span = total_arc * (c.size / total)
        if span < min_arc:
            skipped_size += c.size
            skipped_count += 1
        else:
            rendered.append((c, span))
    if (
        skipped_count > 0
        and skipped_size > 0
        and skipped_size / total >= _OTHER_VISIBLE_FRAC
    ):
        other = TreeNode(
            OTHER_MARKER + " " + _("({n} items)").format(n=skipped_count),
            skipped_size,
            is_dir=False,
        )
        rendered.append((other, total_arc * skipped_size / total))
        rendered.sort(key=lambda x: -x[0].size)
        node.children.append(other)
    a = start_angle
    for i, (c, span) in enumerate(rendered):
        child_top = i if depth == 0 else top_idx
        layout_sunburst(
            c, cx, cy, r_inner + r_step, r_step,
            max_depth, a, a + span, depth + 1, child_top, min_arc,
        )
        a += span


def sunburst_hit_test(
    node: TreeNode,
    mx: float,
    my: float,
    depth: int = 0,
    max_depth: int = _DEFAULT_MAX_DEPTH,
) -> Optional[TreeNode]:
    """Polar koordinatla fareye denk gelen en derin düğümü bul.

    ``max_depth`` stale rect'leri (drill-in/out kalıntıları) görmezden gelir.
    """
    if depth > max_depth:
        return None
    if node.rect is None or len(node.rect) < 6:
        return None
    cx, cy, r_in, r_out, a0, a1 = node.rect[:6]
    dx, dy = mx - cx, my - cy
    r = (dx * dx + dy * dy) ** 0.5
    for c in node.children:
        hit = sunburst_hit_test(c, mx, my, depth + 1, max_depth)
        if hit:
            return hit
    if r < r_in or r > r_out:
        return None
    angle = math.atan2(dy, dx)
    while angle < a0:
        angle += 2 * math.pi
    if angle <= a1:
        return node
    return None


class SunburstStrategy(VizStrategy):
    """:class:`VizStrategy` implementasyonu — sunburst (radial).

    ``draw`` UI panel'inde (Faz G'de buraya taşınacak).
    """

    name = "sunburst"

    def __init__(
        self,
        max_depth: int = _DEFAULT_MAX_DEPTH,
        min_arc: float = _DEFAULT_MIN_ARC,
    ) -> None:
        self.max_depth = max_depth
        self.min_arc = min_arc

    def layout(self, node: TreeNode, w: float, h: float) -> None:
        cx = w / 2
        cy = h / 2
        # Halka adımı min(w, h)/4 — UI panel'in eski hesabıyla uyumlu.
        r_step = min(w, h) / (2 * (self.max_depth + 1))
        layout_sunburst(
            node, cx, cy, r_inner=r_step / 2, r_step=r_step,
            max_depth=self.max_depth, min_arc=self.min_arc,
        )

    def hit_test(self, node: TreeNode, x: float, y: float) -> Optional[TreeNode]:
        return sunburst_hit_test(node, x, y, max_depth=self.max_depth)


__all__ = ["SunburstStrategy", "layout_sunburst", "sunburst_hit_test"]
