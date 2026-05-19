"""Filesystem scanners — pure, UI-independent.

All functions:

- exit quickly once ``cancel`` is set
- emit short human-readable text via ``progress`` (if provided; wrap
  with ThrottledProgress)
- perform I/O but their results are pure computations — tests can call
  them directly with tmp_path.
"""

from __future__ import annotations

import hashlib
import os
import stat as statmod
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any

from ..i18n import _
from ..utils import human
from .sizing import dir_size

# Build artifact directory names — find_project_artifacts looks for these.
ARTIFACT_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        "target",
        "build",
        "dist",
        ".next",
        ".nuxt",
        "out",
        "bin",
        "obj",
        "__pycache__",
        ".pytest_cache",
        "venv",
        ".venv",
        ".gradle",
        ".cargo-target",
    }
)

# Default risk level keyed by artifact name.
ARTIFACT_RISK: dict[str, str] = {
    "node_modules": "low",
    "target": "low",
    "build": "low",
    "dist": "low",
    ".next": "low",
    ".nuxt": "low",
    "out": "medium",
    "bin": "medium",
    "obj": "low",
    "__pycache__": "low",
    ".pytest_cache": "low",
    "venv": "medium",
    ".venv": "medium",
    ".gradle": "low",
    ".cargo-target": "low",
}

_IMAGE_EXTS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".gif",
    }
)

# Directory names that os.walk should never descend into.
_SKIP_WALK_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".cache",
    }
)


def find_project_artifacts(
    root: str | Path,
    cancel: Event | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[str]:
    """Find build / cache artifact folders under ``root``.

    Once an artifact is found, do not descend into it (nested artifacts
    are not needed).
    """
    root = Path(root).expanduser()
    if not root.exists():
        return []
    found: list[str] = []
    for dirpath, dirnames, _files in os.walk(root, followlinks=False):
        if cancel is not None and cancel.is_set():
            break
        if progress is not None:
            progress(_("{n} artifacts · {path}").format(n=len(found), path=dirpath))
        keep_dirs: list[str] = []
        for d in list(dirnames):
            full = os.path.join(dirpath, d)
            if d in ARTIFACT_DIRS:
                found.append(full)
            elif d == ".git":
                continue
            else:
                keep_dirs.append(d)
        dirnames[:] = keep_dirs
    return found


def find_git_root(path: str | Path) -> Path | None:
    """Walk up to find a ``.git`` directory; None if not found."""
    p = Path(path).parent
    while True:
        if (p / ".git").exists():
            return p
        if p == p.parent:
            return None
        p = p.parent


def project_activity_days(artifact_path: str | Path) -> float | None:
    """Last activity age (in days) of the parent project. None if no ``.git``."""
    git_root = find_git_root(artifact_path)
    if not git_root:
        return None
    candidates = [
        git_root / ".git" / "HEAD",
        git_root / ".git" / "FETCH_HEAD",
        git_root / ".git" / "ORIG_HEAD",
        git_root / ".git" / "index",
    ]
    newest = 0.0
    for c in candidates:
        if c.exists():
            newest = max(newest, c.stat().st_mtime)
    if newest == 0:
        return None
    return (time.time() - newest) / 86400


def list_dir_children(path: str | Path) -> list[str]:
    """Return one-level children under ``path``."""
    p = Path(path).expanduser()
    if not p.exists() or not p.is_dir():
        return []
    try:
        return [str(child) for child in p.iterdir()]
    except PermissionError:
        return []


def find_old_files(folder: str | Path, days: int) -> list[tuple[str, int, float]]:
    """Return one-level children of ``folder`` older than ``days`` days.

    Returns ``[(path, size, mtime), ...]`` — sorted by size descending.
    """
    p = Path(folder).expanduser()
    if not p.exists():
        return []
    cutoff = time.time() - days * 86400
    out: list[tuple[str, int, float]] = []
    try:
        for entry in p.iterdir():
            try:
                st = entry.stat()
            except OSError:
                continue
            if st.st_mtime < cutoff:
                size = st.st_size if entry.is_file() else dir_size(entry)
                out.append((str(entry), size, st.st_mtime))
    except PermissionError:
        return []
    out.sort(key=lambda x: -x[1])
    return out


def _dhash(path: str | Path) -> int | None:
    """64-bit difference hash. Requires Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as img:
            img = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())
    except Exception:
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def find_similar_images(
    folder: str | Path,
    cancel: Event | None = None,
    progress: Callable[[str], None] | None = None,
    threshold: int = 5,
    min_size: int = 20 * 1024,
) -> dict[str, Any]:
    """Find visually similar photos (dHash + hamming ≤ threshold).

    ``threshold=5``: nearly identical; higher = more permissive.
    Returns ``{"groups": [[path, ...], ...], "scanned": int}`` or
    ``{"error": "..."}`` if Pillow is missing.
    """
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return {"error": _("Pillow not available — `pip install pillow` required")}
    folder = Path(folder).expanduser()
    if not folder.exists():
        return {"error": _("path not found: {p}").format(p=folder)}

    candidates: list[str] = []
    for root, dirs, files in os.walk(folder, followlinks=False):
        if cancel is not None and cancel.is_set():
            return {"groups": [], "scanned": 0}
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            full = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext not in _IMAGE_EXTS:
                continue
            try:
                if os.path.getsize(full) < min_size:
                    continue
            except OSError:
                continue
            candidates.append(full)

    if progress is not None:
        progress(_("{n} images found, hashing…").format(n=len(candidates)))

    hashes: list[tuple[str, int]] = []
    for idx, p in enumerate(candidates):
        if cancel is not None and cancel.is_set():
            return {"groups": [], "scanned": idx}
        if progress is not None and idx % 20 == 0:
            progress(
                _("hash {i}/{n} · {name}").format(
                    i=idx, n=len(candidates), name=os.path.basename(p)
                )
            )
        h = _dhash(p)
        if h is not None:
            hashes.append((p, h))

    # Grouping: O(n²) — a BK-tree would be better for large sets, but this is enough.
    groups: list[list[str]] = []
    used: set[int] = set()
    for i in range(len(hashes)):
        if i in used:
            continue
        if cancel is not None and cancel.is_set():
            break
        group = [hashes[i][0]]
        used.add(i)
        for j in range(i + 1, len(hashes)):
            if j in used:
                continue
            if _hamming(hashes[i][1], hashes[j][1]) <= threshold:
                group.append(hashes[j][0])
                used.add(j)
        if len(group) >= 2:
            # Keep the highest resolution/size first (assume large = original).
            group.sort(key=lambda x: -os.path.getsize(x))
            groups.append(group)

    return {"groups": groups, "scanned": len(candidates)}


def find_empty_items(
    folder: str | Path,
    cancel: Event | None = None,
    progress: Callable[[str], None] | None = None,
    include_zero_byte: bool = True,
) -> tuple[list[str], list[str]]:
    """Find empty directories and 0-byte files.

    Does not descend into ``.git/``, ``node_modules/``, ``__pycache__/``,
    ``.cache/``. Returns ``(empty_dirs, zero_byte_files)``.
    """
    folder = Path(folder).expanduser()
    if not folder.exists():
        return [], []
    empty_dirs: list[str] = []
    zero_files: list[str] = []
    scanned = 0
    for root, dirs, files in os.walk(folder, followlinks=False, topdown=False):
        if cancel is not None and cancel.is_set():
            return [], []
        dirs[:] = [d for d in dirs if d not in _SKIP_WALK_DIRS]
        scanned += 1
        if progress is not None and scanned % 50 == 0:
            progress(
                _("{dirs} empty folders · {files} 0-byte files · {root}").format(
                    dirs=len(empty_dirs), files=len(zero_files), root=root
                )
            )
        if include_zero_byte:
            for f in files:
                full = os.path.join(root, f)
                try:
                    if os.path.getsize(full) == 0:
                        zero_files.append(full)
                except OSError:
                    continue
        # Is the directory empty? (with topdown=False children are already processed)
        try:
            if not os.listdir(root):
                empty_dirs.append(root)
        except OSError:
            continue
    return empty_dirs, zero_files


def find_duplicates(
    folder: str | Path,
    cancel: Event | None = None,
    progress: Callable[[str], None] | None = None,
    min_size: int = 1024 * 1024,
) -> list[tuple[int, list[str]]]:
    """Find groups of files with identical content.

    First match by size (cheap), then content-hash the matching groups
    with blake2b. Files below ``min_size`` are skipped. Returns
    ``[(size, [path, ...]), ...]`` — sorted by size × duplicate count
    descending.
    """
    folder = Path(folder).expanduser()
    if not folder.exists():
        return []
    by_size: dict[int, list[str]] = {}
    file_count = 0
    for root, dirs, files in os.walk(folder, followlinks=False):
        if cancel is not None and cancel.is_set():
            return []
        dirs[:] = [d for d in dirs if d not in _SKIP_WALK_DIRS]
        if progress is not None:
            progress(_("1/2 scanning files · {n} · {root}").format(n=file_count, root=root))
        for f in files:
            full = os.path.join(root, f)
            try:
                st = os.lstat(full)
            except OSError:
                continue
            if not statmod.S_ISREG(st.st_mode):
                continue
            file_count += 1
            if st.st_size < min_size:
                continue
            by_size.setdefault(st.st_size, []).append(full)

    candidate_groups = [(s, p) for s, p in by_size.items() if len(p) >= 2]
    total_to_hash = sum(len(p) for _, p in candidate_groups)
    hashed = 0
    groups: list[tuple[int, list[str]]] = []
    for size, paths in candidate_groups:
        if cancel is not None and cancel.is_set():
            break
        by_hash: dict[str, list[str]] = {}
        for p in paths:
            if cancel is not None and cancel.is_set():
                break
            if progress is not None:
                progress(
                    _("2/2 hash · {i}/{n} · {name} ({size})").format(
                        i=hashed,
                        n=total_to_hash,
                        name=os.path.basename(p),
                        size=human(size),
                    )
                )
            try:
                h = hashlib.blake2b(digest_size=16)
                with open(p, "rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        h.update(chunk)
                by_hash.setdefault(h.hexdigest(), []).append(p)
            except OSError:
                pass
            hashed += 1
        for group in by_hash.values():
            if len(group) >= 2:
                group.sort(key=lambda x: -os.path.getmtime(x))
                groups.append((size, group))
    groups.sort(key=lambda g: -g[0] * (len(g[1]) - 1))
    return groups


__all__ = [
    "ARTIFACT_DIRS",
    "ARTIFACT_RISK",
    "find_project_artifacts",
    "find_git_root",
    "project_activity_days",
    "list_dir_children",
    "find_old_files",
    "find_similar_images",
    "find_empty_items",
    "find_duplicates",
]
