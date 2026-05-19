"""Color palette for treemap/sunburst.

Consistent by top-level child index (same branch always gets the same
hue) with a slight depth shift for layer separation. Two themes:

- **dark**: low saturation (pastel/soft), mid lightness — calm tones
  that don't strain the eye on a dark background.
- **light**: high saturation (vivid/bright), mid-to-upper lightness —
  energetic tones that stay distinguishable on a white background.

``dark`` is passed as a parameter — calling ``theme.is_dark_theme()`` is
the caller's responsibility (no Gtk dependency here).
"""
from __future__ import annotations

import colorsys


def node_color(top_idx: int, depth: int, *, dark: bool, is_other: bool = False) -> tuple[float, float, float]:
    """Return RGB ``(r, g, b)`` (each component in 0..1).

    ``is_other`` is for 'Other' bundles that collect small items: a
    neutral gray palette (avoids the colored-salad effect).
    """
    if is_other:
        v = (0.40 + min(depth, 4) * 0.03) if dark else (0.85 - min(depth, 4) * 0.05)
        return (v, v, v)
    base_hue = (top_idx * 0.618 + 0.08) % 1.0
    hue = (base_hue + depth * 0.015) % 1.0
    if dark:
        # pastel-on-dark: mid lightness + low saturation
        lightness = min(0.60, 0.50 + min(depth, 5) * 0.02)
        sat = max(0.18, 0.32 - min(depth, 5) * 0.03)
    else:
        # vivid-on-light: mid lightness + high saturation
        lightness = min(0.68, 0.55 + min(depth, 5) * 0.03)
        sat = max(0.55, 0.85 - min(depth, 5) * 0.05)
    return colorsys.hls_to_rgb(hue, lightness, sat)


__all__ = ["node_color"]
