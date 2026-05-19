"""Boyut hesaplama yardımcıları — gerçek (block-based) vs nominal.

Önceden ``du -sb`` (apparent size) kullanılıyordu; Docker.raw gibi sparse
dosyalarda 10× yanlış raporluyordu. Şimdi ``du -sB1`` (block-based) ile
gerçek disk kullanımı baz alınır.
"""
from __future__ import annotations

import stat as statmod
from pathlib import Path

from ..utils import run

_SPARSE_DIFF_THRESHOLD = 100 * 1024 * 1024  # 100 MB altı sparse kabul edilmez


def dir_size(path: str | Path) -> int:
    """Dizinin gerçek disk kullanımı (byte). Yoksa 0."""
    p = Path(path).expanduser()
    if not p.exists():
        return 0
    rc, out = run(["du", "-sB1", str(p)])
    if rc != 0:
        return 0
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return 0


def path_size(path: str | Path) -> int:
    """Dosya veya dizin için gerçek disk kullanımı.

    Dosyalarda ``st_blocks * 512`` — sparse dosyalar için doğru gerçek
    boyut. Dizinler için ``dir_size`` (du) kullanır.
    """
    p = Path(path).expanduser()
    if not p.exists() and not p.is_symlink():
        return 0
    try:
        st = p.lstat()
    except OSError:
        return 0
    if statmod.S_ISDIR(st.st_mode) and not statmod.S_ISLNK(st.st_mode):
        return dir_size(p)
    return st.st_blocks * 512


def apparent_size(path: str | Path) -> int:
    """Sembolik/nominal boyut. Sparse dosyalarda gerçek değerden farklı."""
    p = Path(path).expanduser()
    if not p.exists() and not p.is_symlink():
        return 0
    try:
        return p.lstat().st_size
    except OSError:
        return 0


def is_sparse(path: str | Path) -> bool:
    """Dosya sparse mi? Gerçek block kullanımı nominal'in %90'ından küçükse
    ve fark en az 100 MB ise sparse kabul edilir.
    """
    real = path_size(path)
    nominal = apparent_size(path)
    if nominal == 0:
        return False
    return real < nominal * 0.9 and (nominal - real) >= _SPARSE_DIFF_THRESHOLD


__all__ = ["dir_size", "path_size", "apparent_size", "is_sparse"]
