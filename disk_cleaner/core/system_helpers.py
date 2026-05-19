"""System cache/cleanup helpers.

Size measurers and cleanup actions for docker / apt / journal / snap /
firefox / flatpak. These are classic functions returning ``(rc, msg)``,
not subclasses of the :class:`~disk_cleaner.cleaners.Cleaner` ABC —
SYSTEM_TASKS calls them directly as ``clean_fn``. They become Cleaner
classes in phase E.

Functions that need ``TRASH_MODE`` and ``DRY_RUN`` read the values at
call time via :mod:`disk_cleaner.runtime` — runtime is mutable, late
binding.
"""
from __future__ import annotations

from pathlib import Path

from ..i18n import _
from ..utils import parse_size, run
from .safe_remove import rm_contents, safe_remove
from .sizing import dir_size


# ---------- Size measurers ----------


def size_docker_builder() -> int | None:
    """Extract the Build Cache line from ``docker system df`` output."""
    rc, out = run(["docker", "system", "df"])
    if rc != 0:
        return None
    for line in out.splitlines():
        if "Build Cache" in line:
            toks = [
                t for t in line.split()
                if t and t[0].isdigit() and t[-1] in "BkMGT" or t.endswith("kB")
            ]
            for t in toks[::-1]:
                v = parse_size(t)
                if v:
                    return v
    return None


def size_docker_dangling_images() -> int:
    rc, out = run(["docker", "images", "-f", "dangling=true", "-q"])
    if rc != 0 or not out.strip():
        return 0
    total = 0
    for img_id in out.strip().splitlines():
        rc2, out2 = run(
            ["docker", "image", "inspect", img_id, "--format", "{{.Size}}"]
        )
        if rc2 == 0:
            try:
                total += int(out2.strip())
            except ValueError:
                pass
    return total


def size_docker_stopped_containers() -> int:
    rc, out = run([
        "docker", "ps", "-a", "--filter", "status=exited",
        "--format", "{{.Size}}",
    ])
    if rc != 0:
        return 0
    total = 0
    for line in out.splitlines():
        s = line.split()[0] if line.strip() else ""
        total += parse_size(s)
    return total


def size_apt() -> int:
    return dir_size("/var/cache/apt/archives")


def size_journal() -> int | None:
    """Extract a byte count from ``journalctl --disk-usage`` output."""
    rc, out = run(["journalctl", "--disk-usage"])
    if rc != 0:
        return None
    mult_map = {"B": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}
    for tok in out.split():
        if tok and tok[0].isdigit() and tok[-1] in "BKMGT":
            try:
                val = float(tok.rstrip("BKMGT"))
            except ValueError:
                continue
            return int(val * mult_map.get(tok[-1], 1))
    return None


def size_snap_disabled() -> int | None:
    """Total size of disabled snap revisions."""
    rc, out = run(["snap", "list", "--all"])
    if rc != 0:
        return None
    total = 0
    for line in out.splitlines():
        low = line.lower()
        if "disabled" in low :
            parts = line.split()
            if len(parts) >= 3:
                p = Path(f"/var/lib/snapd/snaps/{parts[0]}_{parts[2]}.snap")
                if p.exists():
                    total += p.stat().st_size
    return total


def size_flatpak_unused() -> int | None:
    """``flatpak uninstall --unused`` dry-run; "Nothing unused" → 0, error → None."""
    rc, out = run(
        ["flatpak", "uninstall", "--unused", "--noninteractive",
         "--assumeyes", "--dry-run"],
        timeout=60,
    )
    if rc != 0:
        return None
    if "Nothing unused" in out or not out.strip():
        return 0
    return None


# ---------- Firefox ----------


def _firefox_profile_dirs() -> list[Path]:
    """Return Firefox profiles that contain a cache2 subfolder."""
    base = Path("~/.mozilla/firefox").expanduser()
    if not base.exists():
        return []
    return [p for p in base.iterdir() if p.is_dir() and (p / "cache2").exists()]


def size_firefox_cache() -> int:
    return sum(dir_size(prof / "cache2") for prof in _firefox_profile_dirs())


def clean_firefox_cache() -> tuple[int, str]:
    """Empty ``cache2`` contents in all Firefox profiles via ``safe_remove``."""
    n = 0
    errs: list[str] = []
    for prof in _firefox_profile_dirs():
        target = prof / "cache2"
        if not target.exists():
            continue
        try:
            for child in target.iterdir():
                try:
                    safe_remove(child)
                    n += 1
                except Exception as e:
                    errs.append(f"{child}: {e}")
        except OSError as e:
            errs.append(str(e))
    msg = _("{n} cache items cleaned").format(n=n)
    if errs:
        return 1, msg + "\n" + "\n".join(errs[:5])
    return 0, msg


# ---------- Bulk deletion ----------


def _clean_multi(paths: list[str]) -> tuple[int, str]:
    """Call ``rm_contents`` for multiple paths and combine the results."""
    cleaned = 0
    errs: list[str] = []
    for p in paths:
        if not Path(p).expanduser().exists():
            continue
        rc, msg = rm_contents(p)
        if rc != 0:
            errs.append(msg)
        else:
            cleaned += 1
    out_msg = _("{n} folders cleaned").format(n=cleaned)
    if errs:
        return 1, out_msg + "\n" + "\n".join(errs)
    return 0, out_msg


# ---------- Snap ----------


def clean_snap_disabled_action() -> tuple[int, str]:
    """Remove disabled snap revisions via pkexec. Honors DRY_RUN."""
    from .. import runtime

    rc, out = run(["snap", "list", "--all"])
    if rc != 0:
        return rc, out
    targets: list[tuple[str, str]] = []
    for line in out.splitlines():
        low = line.lower()
        if "disabled" in low :
            parts = line.split()
            if len(parts) >= 3:
                targets.append((parts[0], parts[2]))
    if not targets:
        return 0, _("No disabled snaps to remove")
    if runtime.DRY_RUN:
        return 0, _("[DRY] snaps to remove:") + "\n" + "\n".join(
            f"  {n} rev {r}" for n, r in targets
        )
    log: list[str] = []
    for name, rev in targets:
        rc2, out2 = run(["pkexec", "snap", "remove", name, f"--revision={rev}"])
        status = "ok" if rc2 == 0 else _("error")
        log.append(f"{name} rev {rev}: {status}")
        if rc2 != 0:
            log.append(out2.strip()[:300])
    return 0, "\n".join(log)


# ---------- ~/.cache (except Chrome) ----------


def clean_cache_except_chrome() -> tuple[int, str]:
    """Move everything under ``~/.cache`` to trash; ``google-chrome`` is preserved."""
    from .. import runtime

    p = Path("~/.cache").expanduser()
    if not p.exists():
        return 0, _("~/.cache not found")
    errors: list[str] = []
    n = 0
    for child in p.iterdir():
        if child.name == "google-chrome":
            continue
        try:
            safe_remove(child)
            n += 1
        except Exception as e:
            errors.append(f"{child.name}: {e}")
    mode = _("moved to trash") if runtime.TRASH_MODE else _("deleted")
    msg = _("~/.cache: {n} items {mode} (chrome preserved)").format(n=n, mode=mode)
    if errors:
        return 1, msg + "\n" + _("errors:") + "\n" + "\n".join(errors)
    return 0, msg


__all__ = [
    "_clean_multi",
    "_firefox_profile_dirs",
    "clean_cache_except_chrome",
    "clean_firefox_cache",
    "clean_snap_disabled_action",
    "size_apt",
    "size_docker_builder",
    "size_docker_dangling_images",
    "size_docker_stopped_containers",
    "size_firefox_cache",
    "size_flatpak_unused",
    "size_journal",
    "size_snap_disabled",
]
