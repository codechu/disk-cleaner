"""Safe delete: trash by default, permanent only when explicitly requested.

``TRASH_MODE`` and ``DRY_RUN`` are runtime-mutable globals — UI
checkboxes change them. They live in :mod:`disk_cleaner.runtime`; the
functions in this module read them **at call time** (late binding) to
avoid import-order issues.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..config import HOME
from ..i18n import _
from ..utils import run


def rm_path(path: str | Path) -> None:
    """Irreversible deletion."""
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return
    if p.is_symlink() or p.is_file():
        p.unlink()
    else:
        shutil.rmtree(p)


def _is_inside_trash(p: str | Path) -> bool:
    """Is the path inside the trash directory? Prevents a trash-to-trash loop."""
    try:
        rp = Path(p).resolve()
    except Exception:
        return False
    trash_roots: list[Path | None] = []
    legacy = HOME / ".local" / "share" / "Trash"
    if legacy.exists():
        trash_roots.append(legacy.resolve())
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        t = Path(xdg) / "Trash"
        if t.exists():
            trash_roots.append(t.resolve())
    for tr in trash_roots:
        if tr is None:
            continue
        try:
            rp.relative_to(tr)
            return True
        except ValueError:
            continue
    return False


def _flags() -> tuple[bool, bool]:
    """Read TRASH_MODE / DRY_RUN from :mod:`runtime` at call time."""
    from .. import runtime

    return bool(runtime.TRASH_MODE), bool(runtime.DRY_RUN)


def safe_remove(path: str | Path) -> str:
    """Delete via ``gio trash`` if ``TRASH_MODE`` is on; otherwise permanent.

    If the path is already inside the trash, forces permanent deletion
    (prevents an infinite loop). When ``DRY_RUN`` is on, nothing is
    deleted.
    """
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return _("not found, skipped")
    trash_mode, dry_run = _flags()
    if dry_run:
        return _("[DRY] would have deleted: {p}").format(p=p)
    if trash_mode and not _is_inside_trash(p):
        rc, out = run(["gio", "trash", str(p)])
        if rc == 0:
            return _("moved to trash")
        raise RuntimeError(_("gio trash error: {msg}").format(msg=out.strip()[:200]))
    rm_path(p)
    return _("permanently deleted") if trash_mode else _("deleted")


def rm_contents(path: str | Path, force_permanent: bool = False) -> tuple[int, str]:
    """Remove every item inside the directory.

    ``force_permanent=True``: ignore TRASH_MODE and delete permanently —
    used by the trash-emptying flow.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return 0, _("{path} not found, skipped").format(path=path)
    moved = 0
    errs: list[str] = []
    for child in p.iterdir():
        try:
            if force_permanent:
                rm_path(child)
            else:
                safe_remove(child)
            moved += 1
        except Exception as e:
            errs.append(f"{child.name}: {e}")
    trash_mode, _dry = _flags()
    if force_permanent:
        mode = _("permanently deleted")
    else:
        mode = _("moved to trash") if trash_mode else _("deleted")
    msg = _("{n} items {mode}").format(n=moved, mode=mode)
    if errs:
        return 1, msg + "\n" + _("errors:") + "\n" + "\n".join(errs)
    return 0, msg


__all__ = ["rm_path", "safe_remove", "rm_contents"]
