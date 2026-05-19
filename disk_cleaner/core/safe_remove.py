"""Güvenli silme: çöp kutusu varsayılan, kalıcı silme yalnızca açıkça istendiğinde.

``TRASH_MODE`` ve ``DRY_RUN`` runtime mutable globaller — UI'daki kutular
değiştirir. :mod:`disk_cleaner.runtime` modülünde yaşarlar; bu modülün
fonksiyonları onları **çağrı anında** okur (geç bağlama), böylece
import sırası problemine yol açmaz.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..config import HOME
from ..i18n import _
from ..utils import run


def rm_path(path: str | Path) -> None:
    """Geri dönüşsüz silme."""
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return
    if p.is_symlink() or p.is_file():
        p.unlink()
    else:
        shutil.rmtree(p)


def _is_inside_trash(p: str | Path) -> bool:
    """Yol çöp klasörünün içinde mi? Çöpe-çöp döngüsünü engellemek için."""
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
    """Çağrı anında TRASH_MODE / DRY_RUN değerlerini :mod:`runtime`'den oku."""
    from .. import runtime

    return bool(runtime.TRASH_MODE), bool(runtime.DRY_RUN)


def safe_remove(path: str | Path) -> str:
    """``TRASH_MODE`` açıksa ``gio trash`` ile, değilse kalıcı sil.

    Yol zaten çöp kutusunun içindeyse zorunlu kalıcı silme yapar (sonsuz
    döngüyü engeller). ``DRY_RUN`` açıkken hiçbir şey silmez.
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
    """Dizin içindeki her öğeyi kaldır.

    ``force_permanent=True``: TRASH_MODE'u yoksay, kalıcı sil — çöp
    boşaltma akışında kullanılır.
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
