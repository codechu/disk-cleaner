# SPDX-License-Identifier: GPL-3.0-or-later

"""Visualization subpackage — thin re-export shim over ``codechu_treeviz``.

The actual implementation lives in the published library
``codechu-treeviz`` (see https://github.com/codechu/treeviz-py). This
module exposes the same names disk-cleaner historically imported from
``disk_cleaner.viz`` so existing imports keep working.
"""

from __future__ import annotations

from codechu_treeviz import (
    OTHER_MARKER,
    SizeProvider,
    SunburstStrategy,
    TreemapStrategy,
    TreeNode,
    VizStrategy,
    build_tree,
    hit_test,
    is_hash_like,
    layout_sunburst,
    layout_treemap,
    node_color,
    sunburst_hit_test,
)

__all__ = [
    "OTHER_MARKER",
    "SizeProvider",
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
