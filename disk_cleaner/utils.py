"""Küçük, UI-bağımsız yardımcı fonksiyonlar.

- :func:`run` / :func:`_resolve` — PATH-zenginleştirilmiş subprocess sarmalayıcısı
  (nvm node, ~/.local/bin, snap vb. ek konumları otomatik ekler).
- :func:`human` / :func:`parse_size` — byte ↔ insan-okur biçim çevirimi.
- :class:`ThrottledProgress` — UI thread'ini boğmayan callback hız sınırlayıcı.
- :func:`list_real_mounts` — ``findmnt`` üstünden gerçek mount noktaları
  (snap loop, tmpfs, fuse.portal vb. dışlanır).
"""
from __future__ import annotations

import glob as _glob
import json
import os
import shutil
import subprocess
import time
from typing import Any, Callable, Iterable, Optional

from .config import HOME
from .i18n import _

# Komut adı yalın geldiğinde aranacak ek yollar.
# Kullanıcı kurulumları önce — sandboxlı snap'leri sonradan dene.
_EXTRA_BIN_DIRS: list[str] = [
    str(HOME / ".local" / "bin"),
    str(HOME / ".bun" / "bin"),
    str(HOME / ".cargo" / "bin"),
    str(HOME / ".dotnet" / "tools"),
]
# nvm altındaki node sürümleri (en yenisi önce)
_EXTRA_BIN_DIRS += sorted(
    _glob.glob(str(HOME / ".nvm" / "versions" / "node" / "*" / "bin")),
    reverse=True,
)
_EXTRA_BIN_DIRS += [
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/snap/bin",  # sandboxlı sürümler — son çare
]


def _resolve(cmd: list[str] | tuple[str, ...]) -> list[str] | tuple[str, ...]:
    """Komutun ilk elemanı yalın bir ad ise gerçek yolunu bul."""
    if not cmd:
        return cmd
    name = cmd[0]
    if not isinstance(name, str) or "/" in name:
        return cmd
    found = shutil.which(name)
    if found:
        return [found] + list(cmd[1:])
    for d in _EXTRA_BIN_DIRS:
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return [candidate] + list(cmd[1:])
    return cmd  # bulamadık; orijinal hatayla başarısız olsun


def run(
    cmd: list[str] | str,
    shell: bool = False,
    timeout: float = 600,
) -> tuple[int, str]:
    """Subprocess çağrısı — PATH zenginleştirilmiş, hata yutmaz.

    Returns ``(returncode, stdout + stderr birleşik)``. Exception olursa
    ``(1, "hata: ...")`` döner — çağıran kod hep aynı şekilde ele alır.
    """
    try:
        if not shell and isinstance(cmd, list):
            cmd = _resolve(cmd)
        # Çocuk süreçlerin (örn. npm → env node) ek yolları bulabilmesi için
        # PATH'i ek dizinlerle zenginleştir.
        env = os.environ.copy()
        env["PATH"] = ":".join(_EXTRA_BIN_DIRS) + ":" + env.get("PATH", "")
        r = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, _("error: {e}").format(e=e)


def human(n: float | int | None) -> str:
    """Byte sayısını insan-okur biçime çevir."""
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"


def parse_size(s: str) -> int:
    """``"2.5GB"`` gibi metni byte sayısına çevir. Tanınmazsa 0."""
    s = s.strip()
    if not s:
        return 0
    units = {
        "B": 1,
        "kB": 1024,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
        "TB": 1024 ** 4,
    }
    for u, mult in sorted(units.items(), key=lambda x: -len(x[0])):
        if s.endswith(u):
            try:
                return int(float(s[: -len(u)]) * mult)
            except ValueError:
                return 0
    try:
        return int(s)
    except ValueError:
        return 0


class ThrottledProgress:
    """Geri çağrım hızını sınırlar (varsayılan: en fazla 5 Hz).

    UI thread'ini boğmadan canlı durum göstermek için. ``sink`` ``None``
    ise çağrı no-op'tur — opsiyonel progress callback'leri kolay sarmalar.
    """

    def __init__(self, sink: Optional[Callable[[str], None]], hz: float = 5) -> None:
        self.sink = sink
        self.min_interval = 1.0 / hz
        self.last = 0.0

    def __call__(self, msg: str) -> None:
        if self.sink is None:
            return
        now = time.monotonic()
        if now - self.last < self.min_interval:
            return
        self.last = now
        try:
            self.sink(msg)
        except Exception:
            pass


# Mount listelemede dışlanan dosya sistemleri ve yol önekleri.
_SKIP_MOUNT_FS: frozenset[str] = frozenset({
    "squashfs", "tmpfs", "devtmpfs", "overlay", "overlayfs",
    "fuse.portal", "sysfs", "proc", "cgroup", "cgroup2",
    "autofs", "binfmt_misc", "ramfs", "fusectl",
})
_SKIP_MOUNT_PREFIX: tuple[str, ...] = (
    "/snap/", "/var/snap/", "/proc", "/sys", "/dev",
    "/run/user/", "/run/snapd", "/run/credentials",
)


def list_real_mounts() -> list[dict[str, str]]:
    """``findmnt`` ile gerçek mount noktalarını listele.

    Snap loop, tmpfs, fuse.portal gibi suni / kullanıcıya alakasız
    mount'lar filtrelenir. Her öğe ``{target, source, fstype, size, used,
    avail, pcent}`` şemasında string'lerdir.
    """
    rc, out = run([
        "findmnt", "--real", "--json",
        "-o", "TARGET,SOURCE,FSTYPE,SIZE,USED,AVAIL,USE%",
    ])
    if rc != 0:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    result: list[dict[str, str]] = []

    def walk(item: dict[str, Any]) -> None:
        target = item.get("target", "") or ""
        fst = item.get("fstype", "") or ""
        if (
            fst not in _SKIP_MOUNT_FS
            and not any(target.startswith(p) for p in _SKIP_MOUNT_PREFIX)
            and item.get("size")
        ):
            result.append({
                "target": target,
                "source": item.get("source") or "",
                "fstype": fst,
                "size": item.get("size") or "",
                "used": item.get("used") or "",
                "avail": item.get("avail") or "",
                "pcent": item.get("use%") or "",
            })
        for child in item.get("children", []) or []:
            walk(child)

    for root in data.get("filesystems", []):
        walk(root)
    return result


__all__ = [
    "ThrottledProgress",
    "_resolve",
    "human",
    "list_real_mounts",
    "parse_size",
    "run",
]
