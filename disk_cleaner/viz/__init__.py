"""Visualization subpackage.

- :class:`TreeNode` + :func:`build_tree` — disk map data structure
- :class:`TreemapStrategy` — squarified treemap (Bruls, Huijsen, van Wijk 2000)
- :class:`SunburstStrategy` — radial treemap
- :func:`node_color` — shared color palette (dark/light)
- :func:`is_hash_like` — label helper
"""
from __future__ import annotations

from .colors import node_color
from .strategy import VizStrategy
from .sunburst import SunburstStrategy, layout_sunburst, sunburst_hit_test
from .text import is_hash_like
from .tree_node import TreeNode, build_tree
from .treemap import OTHER_MARKER, TreemapStrategy, hit_test, layout_treemap

__all__ = [
    "OTHER_MARKER",
    "SunburstStrategy",
    "TreeNode",
    "TreemapStrategy",
    "VizStrategy",
    "build_tree",
    "hit_test",
    "is_hash_like",
    "layout_sunburst",
    "layout_treemap",
    "node_color",
    "sunburst_hit_test",
]
