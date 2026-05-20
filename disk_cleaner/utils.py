# SPDX-License-Identifier: GPL-3.0-or-later

"""Small, UI-independent helper functions.

- :func:`run` / :func:`_resolve` — subprocess wrapper with PATH enrichment
  (auto-adds extra locations such as nvm node, ~/.local/bin, snap, etc.).
- :func:`human` / :func:`parse_size` — byte ↔ human-readable format
  conversion.
- :class:`ThrottledProgress` — callback rate limiter that does not flood
  the UI thread.
- :func:`list_real_mounts` — real mount points via ``findmnt``
  (snap loop, tmpfs, fuse.portal, etc. are excluded).
"""

from __future__ import annotations

import glob as _glob
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from typing import Any

from .config import HOME
from .i18n import _

# Extra paths searched when the command name arrives bare.
# User installs first — try sandboxed snap variants last.
_EXTRA_BIN_DIRS: list[str] = [
    str(HOME / ".local" / "bin"),
    str(HOME / ".bun" / "bin"),
    str(HOME / ".cargo" / "bin"),
    str(HOME / ".dotnet" / "tools"),
]
# node versions under nvm (newest first)
_EXTRA_BIN_DIRS += sorted(
    _glob.glob(str(HOME / ".nvm" / "versions" / "node" / "*" / "bin")),
    reverse=True,
)
_EXTRA_BIN_DIRS += [
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/snap/bin",  # sandboxed variants — last resort
]


def _resolve(cmd: list[str] | tuple[str, ...]) -> list[str] | tuple[str, ...]:
    """If the first element of the command is a bare name, find its real path."""
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
    return cmd  # not found; fail with the original error


def run(
    cmd: list[str] | str,
    shell: bool = False,
    timeout: float = 600,
) -> tuple[int, str]:
    """Subprocess call — PATH-enriched, does not swallow errors.

    Returns ``(returncode, stdout + stderr combined)``. On exception,
    returns ``(1, "error: ...")`` — callers always handle it the same way.
    """
    try:
        if not shell and isinstance(cmd, list):
            cmd = _resolve(cmd)
        # Enrich PATH with the extra directories so child processes
        # (e.g. npm → env node) can find the extra paths.
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
    """Convert a byte count to a human-readable format."""
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"


def parse_size(s: str) -> int:
    """Convert text like ``"2.5GB"`` to a byte count. 0 if not recognized."""
    s = s.strip()
    if not s:
        return 0
    units = {
        "B": 1,
        "kB": 1024,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
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
    """Throttle callback rate (default: at most 5 Hz).

    For live status display without flooding the UI thread. If ``sink``
    is ``None`` the call is a no-op — wraps optional progress callbacks
    conveniently.
    """

    def __init__(self, sink: Callable[[str], None] | None, hz: float = 5) -> None:
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


# Filesystems and path prefixes excluded when listing mounts.
_SKIP_MOUNT_FS: frozenset[str] = frozenset(
    {
        "squashfs",
        "tmpfs",
        "devtmpfs",
        "overlay",
        "overlayfs",
        "fuse.portal",
        "sysfs",
        "proc",
        "cgroup",
        "cgroup2",
        "autofs",
        "binfmt_misc",
        "ramfs",
        "fusectl",
    }
)
_SKIP_MOUNT_PREFIX: tuple[str, ...] = (
    "/snap/",
    "/var/snap/",
    "/proc",
    "/sys",
    "/dev",
    "/run/user/",
    "/run/snapd",
    "/run/credentials",
)


def list_real_mounts() -> list[dict[str, str]]:
    """List real mount points via ``findmnt``.

    Artificial / user-irrelevant mounts like snap loop, tmpfs, fuse.portal
    are filtered. Each item is a dict of strings with the schema
    ``{target, source, fstype, size, used, avail, pcent}``.
    """
    rc, out = run(
        [
            "findmnt",
            "--real",
            "--json",
            "-o",
            "TARGET,SOURCE,FSTYPE,SIZE,USED,AVAIL,USE%",
        ]
    )
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
            result.append(
                {
                    "target": target,
                    "source": item.get("source") or "",
                    "fstype": fst,
                    "size": item.get("size") or "",
                    "used": item.get("used") or "",
                    "avail": item.get("avail") or "",
                    "pcent": item.get("use%") or "",
                }
            )
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
