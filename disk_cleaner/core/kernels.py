"""Eski kernel paketleri (Ubuntu / Debian).

Mevcut kernel + en yakın yedek dışındaki tüm linux-image / headers /
modules paketlerini listeler. ``clean_old_kernels`` ``pkexec`` ile apt
purge çalıştırır; DRY_RUN açıkken sadece adları döner.
"""
from __future__ import annotations

import re

from ..i18n import _
from ..utils import run


def _list_kernel_pkgs() -> list[tuple[str, str, int]]:
    """Yüklü tüm linux-image / headers / modules paketlerini döndür.

    Returns ``[(package_name, version_string, size_bytes), ...]``.
    """
    rc, out = run(
        ["dpkg-query", "-W", "-f", "${Status}\\t${Package}\\t${Installed-Size}\\n"]
    )
    if rc != 0:
        return []
    pkgs: list[tuple[str, str, int]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        status, name, size_kb = parts[0], parts[1], parts[2]
        if "install ok installed" not in status:
            continue
        if not re.match(r"^linux-(image|headers|modules|modules-extra)-\d", name):
            continue
        m = re.search(r"(\d+\.\d+\.\d+-\d+)", name)
        if not m:
            continue
        try:
            size_bytes = int(size_kb) * 1024
        except ValueError:
            size_bytes = 0
        pkgs.append((name, m.group(1), size_bytes))
    return pkgs


def _old_kernel_pkgs() -> list[tuple[str, str, int]]:
    """Mevcut + 1 yedek dışındaki paketleri döndür."""
    pkgs = _list_kernel_pkgs()
    if not pkgs:
        return []
    rc, out = run(["uname", "-r"])
    current = out.strip() if rc == 0 else ""
    cur_match = re.match(r"(\d+\.\d+\.\d+-\d+)", current)
    cur_ver = cur_match.group(1) if cur_match else ""
    versions = sorted(
        {v for _, v, _ in pkgs},
        key=lambda v: list(map(int, re.findall(r"\d+", v))),
    )
    if cur_ver and cur_ver in versions:
        keep = {cur_ver}
        below = [v for v in versions if v != cur_ver]
        if below:
            keep.add(below[-1])
    else:
        keep = set(versions[-2:])  # en yeni iki sürüm
    return [(n, v, s) for n, v, s in pkgs if v not in keep]


def size_old_kernels() -> int:
    """Eski kernel paketlerinin toplam disk kullanımı (byte)."""
    return sum(s for _, _, s in _old_kernel_pkgs())


def clean_old_kernels() -> tuple[int, str]:
    """Eski kernel'leri pkexec ile purge et.

    DRY_RUN runtime'da :mod:`disk_cleaner.runtime` üzerinden okunur
    (geç bağlama). Returns ``(returncode, message)``.
    """
    from .. import runtime

    pkgs = _old_kernel_pkgs()
    if not pkgs:
        return 0, _("No old kernels")
    names = [n for n, _v, _s in pkgs]
    if runtime.DRY_RUN:
        return 0, _("[DRY] would purge:") + "\n" + "\n".join(f"  {n}" for n in names)
    cmd = ["pkexec", "apt", "purge", "-y", *names]
    return run(cmd, timeout=900)


# Geriye uyumlu adlar.
list_old_kernels = _old_kernel_pkgs
list_installed_kernels = _list_kernel_pkgs

__all__ = [
    "_list_kernel_pkgs",
    "_old_kernel_pkgs",
    "clean_old_kernels",
    "list_installed_kernels",
    "list_old_kernels",
    "size_old_kernels",
]
