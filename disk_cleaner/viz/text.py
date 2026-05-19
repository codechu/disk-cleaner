"""Treemap/sunburst label helpers."""
from __future__ import annotations

_HEX_CHARS: frozenset[str] = frozenset("0123456789abcdefABCDEF-")


def is_hash_like(name: str) -> bool:
    """True for long hex-like names (uuid, hash, etc.).

    The treemap UI may want to display a shortened/hidden label for these.
    """
    if len(name) < 20:
        return False
    hex_count = sum(1 for c in name if c in _HEX_CHARS)
    return hex_count / len(name) > 0.85


__all__ = ["is_hash_like"]
