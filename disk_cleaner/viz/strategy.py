"""Visualization Strategy ABC.

Treemap ve Sunburst aynı arayüzü implement eder; UI sekme geçerken yalnızca
``VizStrategy`` örneğini değiştirir. Yeni bir görselleştirme (icicle, flame
graph, ...) ``VizStrategy`` alt sınıfı olarak eklenebilir.

Şu an ``layout`` ve ``hit_test`` zorunlu (saf logic, viz alt paketinde).
``draw`` opsiyonel — mevcut implementasyonlar cairo çizimini UI panel'inde
yapıyor (animasyon + hover state ile iç içe). Faz G'de panel
``strategy.draw`` çağrısına bağlanacak.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import cairo

    from .tree_node import TreeNode


class VizStrategy(ABC):
    """Görselleştirme stratejisi — layout + hit-test (zorunlu), draw (ops.)."""

    name: str = "unknown"

    @abstractmethod
    def layout(self, node: "TreeNode", w: float, h: float) -> None:
        """Verilen kanvas boyutunda recursive layout hesapla, node'lara yaz."""

    @abstractmethod
    def hit_test(self, node: "TreeNode", x: float, y: float) -> Optional["TreeNode"]:
        """``(x, y)``'nin altındaki node'u bul (yoksa None)."""

    def draw(
        self,
        cr: "cairo.Context",
        node: "TreeNode",
        *,
        hover: Optional["TreeNode"] = None,
        dark: bool = False,
    ) -> None:
        """Cairo context'e çiz.

        Default implementation şu anda UI panel'i bu işi yapıyor diye
        ``NotImplementedError`` fırlatır. Strategy doğrudan kullanmak için
        alt sınıfta override edin.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.draw is not on the strategy yet — "
            "the UI panel (TreemapPanel/SunburstPanel) does the drawing."
        )


__all__ = ["VizStrategy"]
