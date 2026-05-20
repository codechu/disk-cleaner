# SPDX-License-Identifier: GPL-3.0-or-later

"""Installed application list and related user data folders.

Uses dpkg-query to guess packages installed manually by the user
(filters out kernel + library + language-pack noise).
``app_related_paths`` finds matching ``~/.config``, ``~/.cache``,
``~/.local/share`` subfolders for a package name — so they can be
removed after apt purge.
"""

from __future__ import annotations

from typing import Any

from ..config import HOME
from ..utils import run

_SKIP_PREFIX: tuple[str, ...] = (
    "lib",
    "linux-",
    "python3-",
    "gcc-",
    "perl-",
    "ruby-",
    "fonts-",
    "language-",
)
_SKIP_EXACT: frozenset[str] = frozenset(
    {
        "base-files",
        "base-passwd",
        "bash",
        "coreutils",
        "dash",
        "debconf",
        "diffutils",
        "dpkg",
        "findutils",
        "grep",
        "gzip",
        "hostname",
        "init",
        "login",
        "mount",
        "ncurses-base",
        "passwd",
        "sed",
        "sysvinit-utils",
        "tar",
        "util-linux",
        "systemd",
        "udev",
    }
)


def list_installed_apps(min_size_kb: int = 1024) -> list[dict[str, Any]]:
    """List 'real' application packages installed via dpkg.

    Filters out system packages such as kernels / libraries / language
    packs. Packages below ``min_size_kb`` are skipped. The result is
    sorted by byte size descending.
    """
    rc, out = run(["dpkg-query", "-W", "-f", "${Package}\\t${Installed-Size}\\t${Description}\\n"])
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
    """Guess candidate user data folders for a package name.

    Looks for common variants of the package name (lowercase,
    dash-stripped, first segment) under ``~/.config``, ``~/.cache``,
    and ``~/.local/share``.
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
