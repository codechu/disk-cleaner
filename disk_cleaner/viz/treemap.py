"""Squarified treemap layout (Bruls, Huijsen, van Wijk 2000).

``layout_treemap`` çocukları kareye yakın dikdörtgenlere yerleştirir;
toplamın ``min_frac`` (varsayılan %0.5) altındaki küçük öğeler tek bir
'Diğer' yumağına toplanır — küçük renkli piksel salatası önlenir.

``hit_test`` tek seviyeli çizim için: önce children, yoksa node.
"""
from __future__ import annotations

from typing import Optional

from ..i18n import _
from .strategy import VizStrategy
from .tree_node import TreeNode

# 'Diğer' yumaklarının ayırt edici prefix'i — re-render'da temizlenir.
OTHER_MARKER: str = "__OTHER__"


def layout_treemap(
    node: TreeNode,
    x: float,
    y: float,
    w: float,
    h: float,
    depth: int = 0,
    min_frac: float = 0.005,
) -> None:
    """Squarified treemap yerleşimi — ``node.rect``'leri set eder.

    Sadece bir seviyeyi yerleştirir; drill-in olunca yeniden çağrılır.
    """
    node.rect = (x, y, w, h)
    # Eski 'Diğer' virtual node'larını temizle (yeniden render'da birikme).
    node.children = [c for c in node.children if not c.path.startswith(OTHER_MARKER)]
    if not node.children or w < 2 or h < 2 or node.size == 0:
        return
    children = sorted(node.children, key=lambda c: -c.size)
    total_size = sum(c.size for c in children)
    if total_size <= 0:
        return
    threshold = total_size * min_frac
    big = [c for c in children if c.size >= threshold]
    small = [c for c in children if c.size < threshold]
    if len(small) >= 2:
        other_size = sum(c.size for c in small)
        other = TreeNode(
            OTHER_MARKER + " " + _("({n} items)").format(n=len(small)),
            other_size,
            is_dir=False,
        )
        big.append(other)
        node.children.append(other)
        big.sort(key=lambda c: -c.size)
    area = w * h
    scaled = [(c, c.size / total_size * area) for c in big]
    _squarify(scaled, [], min(w, h), x, y, w, h, depth)


def _worst_ratio(row: list[tuple[TreeNode, float]], length: float) -> float:
    """Satırdaki en kötü en-boy oranı."""
    if not row or length <= 0:
        return float("inf")
    s = sum(a for _, a in row)
    if s <= 0:
        return float("inf")
    rmax = max(a for _, a in row)
    rmin = min(a for _, a in row)
    if rmin <= 0:
        return float("inf")
    return max((length * length * rmax) / (s * s), (s * s) / (length * length * rmin))


def _squarify(
    items: list[tuple[TreeNode, float]],
    row: list[tuple[TreeNode, float]],
    length: float,
    x: float,
    y: float,
    w: float,
    h: float,
    depth: int,
) -> None:
    """İteratif squarify — derin recursion'a düşmez."""
    items = list(items)
    while items:
        head = items[0]
        new_row = row + [head]
        if _worst_ratio(row, length) >= _worst_ratio(new_row, length):
            row = new_row
            items.pop(0)
        else:
            x, y, w, h = _layout_row(row, x, y, w, h)
            row = []
            length = min(w, h) if (w > 0 and h > 0) else length
            if length <= 0:
                return
    if row:
        _layout_row(row, x, y, w, h)


def _layout_row(
    row: list[tuple[TreeNode, float]],
    x: float,
    y: float,
    w: float,
    h: float,
) -> tuple[float, float, float, float]:
    """Satırı kısa kenar boyunca yerleştir. Kullanılmayan alan döndür."""
    if not row:
        return x, y, w, h
    s = sum(a for _, a in row)
    if w >= h:
        col_w = s / h if h > 0 else 0
        pos = 0.0
        for node, area in row:
            ch = (area / col_w) if col_w > 0 else 0
            node.rect = (x, y + pos, col_w, ch)
            pos += ch
        return x + col_w, y, w - col_w, h
    else:
        row_h = s / w if w > 0 else 0
        pos = 0.0
        for node, area in row:
            cw = (area / row_h) if row_h > 0 else 0
            node.rect = (x + pos, y, cw, row_h)
            pos += cw
        return x, y + row_h, w, h - row_h


def hit_test(node: TreeNode, mx: float, my: float, depth: int = 0) -> Optional[TreeNode]:
    """Tek seviyeli treemap çizimi için: önce children, yoksa node.

    Sadece 4-tuple (treemap) rect'leri kabul eder; mod geçişlerinden
    artakalan sunburst rect'leri (7-tuple) sessizce atlanır.
    """
    if node.rect is None or len(node.rect) != 4:
        return None
    for c in node.children:
        if c.rect is None or len(c.rect) != 4:
            continue
        x, y, w, h = c.rect
        if x <= mx <= x + w and y <= my <= y + h:
            return c
    return node


class TreemapStrategy(VizStrategy):
    """:class:`VizStrategy` implementasyonu — squarified treemap.

    ``draw`` şu an UI panel'i (``TreemapPanel.on_draw``) tarafından
    yapılıyor (cairo çizimi animasyon + hover state ile iç içe). Faz G'de
    bu sınıfa taşınacak.
    """

    name = "treemap"

    def __init__(self, min_frac: float = 0.005) -> None:
        self.min_frac = min_frac

    def layout(self, node: TreeNode, w: float, h: float) -> None:
        layout_treemap(node, 0.0, 0.0, float(w), float(h), min_frac=self.min_frac)

    def hit_test(self, node: TreeNode, x: float, y: float) -> Optional[TreeNode]:
        return hit_test(node, x, y)


__all__ = [
    "OTHER_MARKER",
    "TreemapStrategy",
    "hit_test",
    "layout_treemap",
]
