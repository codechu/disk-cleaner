"""Treemap/sunburst etiket yardımcıları."""
from __future__ import annotations

_HEX_CHARS: frozenset[str] = frozenset("0123456789abcdefABCDEF-")


def is_hash_like(name: str) -> bool:
    """Uzun hex-benzeri adlar (uuid, hash, vs.) için True.

    Treemap UI'ı bunlar için kısaltılmış/gizli etiket göstermek isteyebilir.
    """
    if len(name) < 20:
        return False
    hex_count = sum(1 for c in name if c in _HEX_CHARS)
    return hex_count / len(name) > 0.85


__all__ = ["is_hash_like"]
