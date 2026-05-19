"""Size helpers — real (block-based) vs. nominal.

Previously used ``du -sb`` (apparent size); for sparse files like
Docker.raw it overreported by 10×. We now base sizes on ``du -sB1``
(block-based), i.e. real disk usage.
"""

from __future__ import annotations

import stat as statmod
from pathlib import Path

from ..utils import run

_SPARSE_DIFF_THRESHOLD = 100 * 1024 * 1024  # below 100 MB is not considered sparse


def dir_size(path: str | Path) -> int:
    """Real disk usage (bytes) of a directory. 0 if missing."""
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
    """Real disk usage for a file or directory.

    For files: ``st_blocks * 512`` — accurate real size for sparse
    files. For directories: ``dir_size`` (du).
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
    """Symbolic/nominal size. Differs from the real value on sparse files."""
    p = Path(path).expanduser()
    if not p.exists() and not p.is_symlink():
        return 0
    try:
        return p.lstat().st_size
    except OSError:
        return 0


def is_sparse(path: str | Path) -> bool:
    """Is the file sparse? Considered sparse if real block usage is below
    90% of nominal and the difference is at least 100 MB.
    """
    real = path_size(path)
    nominal = apparent_size(path)
    if nominal == 0:
        return False
    return real < nominal * 0.9 and (nominal - real) >= _SPARSE_DIFF_THRESHOLD


__all__ = ["dir_size", "path_size", "apparent_size", "is_sparse"]
