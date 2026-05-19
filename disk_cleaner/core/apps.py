"""Yüklü uygulama listesi ve ilgili kullanıcı veri klasörleri.

dpkg-query üstünden kullanıcının manuel kurduğu paketleri tahmin eder
(kernel + kütüphane + dil-paketi filtreler). ``app_related_paths`` bir
paket adına yakın ``~/.config``, ``~/.cache``, ``~/.local/share`` alt
klasörlerini yakalar — apt purge'dan sonra silmek için.
"""
from __future__ import annotations

from typing import Any

from ..config import HOME
from ..utils import run

_SKIP_PREFIX: tuple[str, ...] = (
    "lib", "linux-", "python3-", "gcc-", "perl-", "ruby-",
    "fonts-", "language-",
)
_SKIP_EXACT: frozenset[str] = frozenset({
    "base-files", "base-passwd", "bash", "coreutils",
    "dash", "debconf", "diffutils", "dpkg", "findutils",
    "grep", "gzip", "hostname", "init", "login", "mount",
    "ncurses-base", "passwd", "sed", "sysvinit-utils",
    "tar", "util-linux", "systemd", "udev",
})


def list_installed_apps(min_size_kb: int = 1024) -> list[dict[str, Any]]:
    """dpkg üzerinde yüklü 'gerçek' uygulama paketlerini listele.

    Kernel / kütüphane / dil-paketi gibi sistem paketleri elenir.
    ``min_size_kb`` altındakiler atlanır. Sonuç byte cinsinden boyuta
    göre azalan sırada.
    """
    rc, out = run(
        ["dpkg-query", "-W", "-f", "${Package}\\t${Installed-Size}\\t${Description}\\n"]
    )
    if rc != 0:
        return []
    pkgs: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        name, size_str, desc = parts[0], parts[1], parts[2]
        if name in _SKIP_EXACT:
            continue
        if any(name.startswith(p) for p in _SKIP_PREFIX):
            continue
        try:
            size = int(size_str) * 1024
        except ValueError:
            size = 0
        if size < min_size_kb * 1024:
            continue
        pkgs.append({"name": name, "size": size, "desc": desc[:80]})
    pkgs.sort(key=lambda p: -p["size"])
    return pkgs


def app_related_paths(pkg_name: str) -> list[str]:
    """Bir paket adı için olası kullanıcı veri klasörlerini tahmin et.

    ``~/.config``, ``~/.cache``, ``~/.local/share`` altında paket adının
    yaygın varyasyonlarını arar (lowercase, tire-siz, ilk parça).
    """
    bases = [HOME / ".config", HOME / ".cache", HOME / ".local" / "share"]
    variants = {
        pkg_name,
        pkg_name.lower(),
        pkg_name.replace("-", ""),
        pkg_name.split("-")[0],
    }
    candidates: list[str] = []
    for base in bases:
        if not base.exists():
            continue
        for v in variants:
            p = base / v
            if p.exists():
                candidates.append(str(p))
    return sorted(set(candidates))


__all__ = ["app_related_paths", "list_installed_apps"]
