"""Visualization Strategy ABC.

Treemap and Sunburst implement the same interface; when the UI
switches tabs, only the ``VizStrategy`` instance changes. New
visualizations (icicle, flame graph, ...) can be added as
``VizStrategy`` subclasses.

For now, ``layout`` and ``hit_test`` are required (pure logic in the
viz subpackage). ``draw`` is optional — current implementations draw
to cairo inside the UI panel (interleaved with animation + hover
state). In phase G the panel wires through to ``strategy.draw``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import cairo

    from .tree_node import TreeNode


class VizStrategy(ABC):
    """Visualization strategy — layout + hit-test (required), draw (optional)."""

    name: str = "unknown"

    @abstractmethod
    def layout(self, node: "TreeNode", w: float, h: float) -> None:
        """Compute recursive layout for the given canvas size and write it onto nodes."""

    @abstractmethod
    def hit_test(self, node: "TreeNode", x: float, y: float) -> Optional["TreeNode"]:
        """Find the node under ``(x, y)`` (None if not present)."""

    def draw(
        self,
        cr: "cairo.Context",
        node: "TreeNode",
        *,
        hover: Optional["TreeNode"] = None,
        dark: bool = False,
    ) -> None:
        """Draw onto a cairo context.

        The default implementation raises ``NotImplementedError`` because
        the UI panel currently performs this work. Override in a subclass
        to use the strategy directly.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.draw is not on the strategy yet — "
            "the UI panel (TreemapPanel/SunburstPanel) does the drawing."
        )


__all__ = ["VizStrategy"]
