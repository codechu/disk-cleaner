"""Task factories + SYSTEM_TASKS — the data source for Scanner classes.

This module hosts the "dict-based task" schema: ``{name, desc, risk,
path, size_fn, clean_fn}``. Scanner classes wrap these factories and
convert them into :class:`~disk_cleaner.scanners.Task` dataclasses.

After phase E, the new OOP surface built on the Scanner ABC is in place,
but broad data lists like SYSTEM_TASKS and a few factories remain here —
they are the stateless "configuration" layer of Scanner classes.

``DRY_RUN`` and ``TRASH_MODE`` are read at call time via
:mod:`disk_cleaner.runtime` (runtime is mutable; the UI may change it).
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cleaners.command import CommandCleaner
from .cleaners.contents import ContentsCleaner
from .cleaners.safe_path import SafePathCleaner
from .config import HOME
from .config import USER_CLEANERS_DIR as CLEANERS_DIR
from .core.apps import app_related_paths, list_installed_apps
from .core.kernels import clean_old_kernels, size_old_kernels
from .core.safe_remove import rm_contents
from .core.sizing import apparent_size, dir_size, is_sparse, path_size
from .core.system_helpers import (
    _clean_multi,
    clean_cache_except_chrome,
    clean_firefox_cache,
    clean_snap_disabled_action,
    size_apt,
    size_docker_builder,
    size_docker_dangling_images,
    size_docker_stopped_containers,
    size_firefox_cache,
    size_flatpak_unused,
    size_journal,
    size_snap_disabled,
)
from .core.walker import (
    ARTIFACT_RISK,
    find_duplicates,
    find_empty_items,
    find_old_files,
    find_project_artifacts,
    find_similar_images,
    list_dir_children,
    project_activity_days,
)
from .i18n import _
from .storage.du_cache import cached_dir_size
from .utils import human, run

# ---------- Cleaner factories (bound to Cleaner.execute) ----------


def make_rm_path_clean(path_str: str) -> Callable[[], tuple[int, str]]:
    return SafePathCleaner(path_str).execute


def make_rm_contents_clean(
    path_str: str, force_permanent: bool = False
) -> Callable[[], tuple[int, str]]:
    return ContentsCleaner(path_str, force_permanent=force_permanent).execute


def make_cmd_clean(
    cmd: list[str] | str, shell: bool = False, need_root: bool = False
) -> Callable[[], tuple[int, str]]:
    return CommandCleaner(cmd, shell=shell, need_root=need_root).execute


# ---------- User-defined rules ----------


def load_user_cleaners() -> list[dict[str, Any]]:
    """Load user rules from ``~/.config/disk_cleaner/cleaners/*.json``.

    Schema::

        {
          "name": "X cache",
          "desc": "description",
          "risk": "low|medium|high",
          "paths": ["~/.x/cache", "~/.local/share/x/cache"],
          "command": ["xtool", "--clear-cache"]   // optional
        }

    If ``paths`` is given, their contents are deleted (honors TRASH_MODE).
    If ``command`` is given, the command runs instead.
    If both are present, ``paths`` runs first, then ``command``.
    """
    if not CLEANERS_DIR.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(CLEANERS_DIR.glob("*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                rule = json.load(f)
        except Exception as e:
            print(f"cleaner load failed {p}: {e}", file=sys.stderr)
            continue
        name = rule.get("name") or p.stem
        desc = rule.get("desc", _("User-defined"))
        risk = rule.get("risk", "medium")
        paths = rule.get("paths") or []
        cmd = rule.get("command")
        display_path = (
            " ".join(paths) if paths else (" ".join(cmd) if isinstance(cmd, list) else (cmd or "?"))
        )

        def make_size_fn(paths=paths):
            if not paths:
                return lambda: 0
            return lambda: sum(dir_size(p) for p in paths)

        def make_clean_fn(paths=paths, cmd=cmd):
            def _do() -> tuple[int, str]:
                msgs = []
                rc_any = 0
                for pp in paths:
                    rc, msg = rm_contents(pp)
                    msgs.append(f"{pp}: {msg}")
                    if rc != 0:
                        rc_any = rc
                if cmd:
                    rc, out = run(cmd, shell=isinstance(cmd, str))
                    msgs.append(f"command: {out.strip()[:200]}")
                    if rc != 0:
                        rc_any = rc
                return rc_any, "\n".join(msgs)

            return _do

        out.append(
            {
                "name": "👤 " + name,
                "desc": desc + _(" (user rule)"),
                "risk": risk,
                "path": display_path,
                "size_fn": make_size_fn(),
                "clean_fn": make_clean_fn(),
            }
        )
    return out


# ---------- Apt application removal ----------


def make_app_uninstall_tasks(
    _unused_arg=None,
    cancel=None,
    progress=None,
) -> list[dict[str, Any]]:
    """Produce tasks for installed apps (and their related user folders).

    Each row = one application. Cleanup: apt purge + related folders.
    DRY_RUN is read at call time from :mod:`disk_cleaner.runtime`.
    """
    if progress:
        progress(_("Listing installed packages…"))
    apps = list_installed_apps(min_size_kb=5 * 1024)  # ≥5 MB
    tasks: list[dict[str, Any]] = []
    for app in apps[:80]:
        if cancel is not None and cancel.is_set():
            break
        name = app["name"]
        related = app_related_paths(name)
        rel_size = sum(dir_size(p) for p in related)
        total = app["size"] + rel_size
        rel_note = (
            _(" + {n} folders ({size})").format(n=len(related), size=human(rel_size))
            if related
            else ""
        )

        def make_clean(name=name, related=related):
            def _do() -> tuple[int, str]:
                from . import runtime

                msgs: list[str] = []
                if runtime.DRY_RUN:
                    msgs.append(f"[DRY] apt purge {name}")
                    for p in related:
                        msgs.append(f"[DRY] {p} would be deleted")
                    return 0, "\n".join(msgs)
                rc, out = run(["pkexec", "apt", "purge", "-y", name], timeout=600)
                msgs.append(
                    f"apt purge {name}: {'ok' if rc == 0 else 'error'}\n{out.strip()[:300]}"
                )
                purge_rc = rc
                for p in related:
                    try:
                        rc2, msg2 = rm_contents(p)
                        try:
                            Path(p).rmdir()
                        except OSError:
                            pass
                        msgs.append(f"{p}: {msg2}")
                    except Exception as e:
                        msgs.append(f"{p}: error {e}")
                return purge_rc, "\n".join(msgs)

            return _do

        tasks.append(
            {
                "name": name,
                "desc": f"{app['desc']}{rel_note}",
                "risk": "high",  # user must remove deliberately
                "path": f"apt:{name}",
                "size_fn": (lambda total=total: total),
                "clean_fn": make_clean(),
            }
        )
    return tasks


# ---------- Walker-based factories ----------


def make_artifact_tasks(
    workspace_root,
    cancel=None,
    progress=None,
    active_threshold_days: int = 14,
) -> list[dict[str, Any]]:
    paths = find_project_artifacts(workspace_root, cancel=cancel, progress=progress)
    tasks: list[dict[str, Any]] = []
    root = Path(workspace_root).expanduser()
    for p in paths:
        rel = os.path.relpath(p, root)
        kind = os.path.basename(p)
        risk = ARTIFACT_RISK.get(kind, "medium")
        desc = _("{kind} folder").format(kind=kind)
        age = project_activity_days(p)
        if age is not None:
            if age < active_threshold_days:
                risk = "high"
                desc = _("⚠ ACTIVE project (last git {days} days ago) — {kind}").format(
                    days=int(age), kind=kind
                )
            else:
                desc = _("{kind} folder • last git {days} days ago").format(
                    kind=kind, days=int(age)
                )
        tasks.append(
            {
                "name": rel,
                "desc": desc,
                "risk": risk,
                "path": p,
                "size_fn": (lambda pp=p: cached_dir_size(pp)),
                "clean_fn": make_rm_path_clean(p),
            }
        )
    return tasks


def make_folder_explorer_tasks(folder, cancel=None) -> list[dict[str, Any]]:
    children = list_dir_children(folder)
    tasks: list[dict[str, Any]] = []
    for c in children:
        name = os.path.basename(c)
        desc = _("child item")
        if is_sparse(c):
            nominal = apparent_size(c)
            desc = _("sparse file (nominal: {size})").format(size=human(nominal))

        def make_size(cc=c):
            return lambda: cached_dir_size(cc) if Path(cc).is_dir() else path_size(cc)

        tasks.append(
            {
                "name": name,
                "desc": desc,
                "risk": "medium",
                "path": c,
                "size_fn": make_size(),
                "clean_fn": make_rm_path_clean(c),
            }
        )
    return tasks


def make_similar_image_tasks(
    folder,
    cancel=None,
    progress=None,
) -> list[dict[str, Any]]:
    result = find_similar_images(folder, cancel=cancel, progress=progress)
    if "error" in result:
        return [
            {
                "name": result["error"],
                "desc": _("installation error"),
                "risk": "high",
                "path": "",
                "size_fn": lambda: 0,
                "clean_fn": lambda: (1, _("Pillow is not installed")),
            }
        ]
    tasks: list[dict[str, Any]] = []
    for group in result["groups"]:
        keep = group[0]
        keep_rel = keep.replace(str(HOME), "~")
        for dup in group[1:]:
            try:
                size = os.path.getsize(dup)
            except OSError:
                size = 0
            tasks.append(
                {
                    "name": os.path.basename(dup),
                    "desc": _("similar to: {path}").format(path=keep_rel),
                    "risk": "medium",
                    "path": dup,
                    "size_fn": (lambda s=size: s),
                    "clean_fn": make_rm_path_clean(dup),
                }
            )
    return tasks


def make_empty_tasks(folder, cancel=None, progress=None) -> list[dict[str, Any]]:
    empty_dirs, zero_files = find_empty_items(folder, cancel=cancel, progress=progress)
    tasks: list[dict[str, Any]] = []
    for d in empty_dirs:
        tasks.append(
            {
                "name": "📁 " + os.path.basename(d) + "/",
                "desc": _("empty folder"),
                "risk": "low",
                "path": d,
                "size_fn": (lambda: 4096),  # a directory inode is ~4KB
                "clean_fn": make_rm_path_clean(d),
            }
        )
    for f in zero_files:
        tasks.append(
            {
                "name": "📄 " + os.path.basename(f),
                "desc": _("0-byte file"),
                "risk": "low",
                "path": f,
                "size_fn": (lambda: 0),
                "clean_fn": make_rm_path_clean(f),
            }
        )
    return tasks


def make_duplicate_tasks(folder, cancel=None, progress=None) -> list[dict[str, Any]]:
    groups = find_duplicates(folder, cancel=cancel, progress=progress)
    tasks: list[dict[str, Any]] = []
    for size, group in groups:
        keep = group[0]
        for dup in group[1:]:
            rel_keep = keep.replace(str(HOME), "~")
            tasks.append(
                {
                    "name": os.path.basename(dup),
                    "desc": _("copy of: {path}").format(path=rel_keep),
                    "risk": "medium",
                    "path": dup,
                    "size_fn": (lambda s=size: s),
                    "clean_fn": make_rm_path_clean(dup),
                }
            )
    return tasks


def make_old_files_tasks(folder, days: int, cancel=None) -> list[dict[str, Any]]:
    items = find_old_files(folder, days)
    tasks: list[dict[str, Any]] = []
    for path, size, mtime in items:
        age_days = int((time.time() - mtime) / 86400)
        tasks.append(
            {
                "name": os.path.basename(path),
                "desc": _("modified {days} days ago").format(days=age_days),
                "risk": "high",
                "path": path,
                "size_fn": (lambda s=size: s),
                "clean_fn": make_rm_path_clean(path),
            }
        )
    return tasks


# ---------- SYSTEM_TASKS — built-in task list ----------

SYSTEM_TASKS: list[dict[str, Any]] = [
    {
        "name": _("Chrome cache"),
        "desc": _("Browser cache. Sessions/passwords are not affected."),
        "risk": "low",
        "path": "~/.cache/google-chrome",
        "size_fn": lambda: dir_size("~/.cache/google-chrome"),
        "clean_fn": make_rm_contents_clean("~/.cache/google-chrome"),
    },
    {
        "name": _("Other ~/.cache contents"),
        "desc": _("Mesa shader cache, fontconfig, etc."),
        "risk": "low",
        "path": "~/.cache (chrome excluded)",
        "size_fn": lambda: max(0, dir_size("~/.cache") - dir_size("~/.cache/google-chrome")),
        "clean_fn": lambda: clean_cache_except_chrome(),
    },
    {
        "name": _("npm cache"),
        "desc": "`npm cache clean --force`.",
        "risk": "low",
        "path": "~/.npm",
        "size_fn": lambda: dir_size("~/.npm"),
        "clean_fn": make_cmd_clean(["npm", "cache", "clean", "--force"]),
    },
    {
        "name": _("Bun cache"),
        "desc": _("Bun package cache."),
        "risk": "low",
        "path": "~/.bun/install/cache",
        "size_fn": lambda: dir_size("~/.bun/install/cache"),
        "clean_fn": make_rm_contents_clean("~/.bun/install/cache"),
    },
    {
        "name": _("Gradle cache"),
        "desc": _("Dependency and build cache."),
        "risk": "low",
        "path": "~/.gradle/caches",
        "size_fn": lambda: dir_size("~/.gradle/caches"),
        "clean_fn": make_rm_contents_clean("~/.gradle/caches"),
    },
    {
        "name": _("Maven repository"),
        "desc": _("JARs will be re-downloaded."),
        "risk": "low",
        "path": "~/.m2/repository",
        "size_fn": lambda: dir_size("~/.m2/repository"),
        "clean_fn": make_rm_contents_clean("~/.m2/repository"),
    },
    {
        "name": _("NuGet cache"),
        "desc": "`dotnet nuget locals all --clear`.",
        "risk": "low",
        "path": "~/.nuget",
        "size_fn": lambda: dir_size("~/.nuget"),
        "clean_fn": make_cmd_clean(["dotnet", "nuget", "locals", "all", "--clear"]),
    },
    {
        "name": _("Docker build cache"),
        "desc": _("`docker builder prune -a -f`. Images/containers not affected."),
        "risk": "low",
        "path": "Docker BuildKit cache",
        "size_fn": size_docker_builder,
        "clean_fn": make_cmd_clean(["docker", "builder", "prune", "-a", "-f"]),
    },
    {
        "name": _("Docker dangling images"),
        "desc": _("Untagged images not attached to any container."),
        "risk": "low",
        "path": "Docker images <none>",
        "size_fn": size_docker_dangling_images,
        "clean_fn": make_cmd_clean(["docker", "image", "prune", "-f"]),
    },
    {
        "name": _("Stopped Docker containers"),
        "desc": _("Removes containers; volumes and images remain."),
        "risk": "medium",
        "path": "exited containers",
        "size_fn": size_docker_stopped_containers,
        "clean_fn": make_cmd_clean(["docker", "container", "prune", "-f"]),
    },
    {
        "name": _("APT cache + autoremove"),
        "desc": _("`apt clean` + `apt autoremove --purge` (root)."),
        "risk": "low",
        "path": "/var/cache/apt",
        "size_fn": size_apt,
        "clean_fn": make_cmd_clean(
            # Static command string — no user-controlled input. shell=True
            # required to chain apt clean + autoremove atomically under pkexec.
            "apt clean && apt autoremove --purge -y",
            shell=True,
            need_root=True,  # nosec B602: vetted static command
        ),
    },
    {
        "name": _("Systemd journal (older than 7 days)"),
        "desc": _("`journalctl --vacuum-time=7d` (root)."),
        "risk": "low",
        "path": "/var/log/journal",
        "size_fn": size_journal,
        "clean_fn": make_cmd_clean(["journalctl", "--vacuum-time=7d"], need_root=True),
    },
    {
        "name": _("Old snap versions"),
        "desc": _("Disabled snap revisions (root)."),
        "risk": "low",
        "path": "/var/lib/snapd/snaps",
        "size_fn": size_snap_disabled,
        "clean_fn": lambda: clean_snap_disabled_action(),
    },
    {
        "name": _("Flatpak unused runtimes"),
        "desc": "`flatpak uninstall --unused`.",
        "risk": "low",
        "path": "/var/lib/flatpak",
        "size_fn": size_flatpak_unused,
        "clean_fn": make_cmd_clean(
            ["flatpak", "uninstall", "--unused", "--noninteractive", "--assumeyes"]
        ),
    },
    {
        "name": _("Empty the trash"),
        "desc": _("Always PERMANENT deletion (trash mode ignored)."),
        "risk": "medium",
        "path": "~/.local/share/Trash",
        "size_fn": lambda: dir_size("~/.local/share/Trash"),
        "clean_fn": make_rm_contents_clean("~/.local/share/Trash", force_permanent=True),
    },
    {
        "name": _("Thumbnail cache"),
        "desc": _("~/.cache/thumbnails — regeneratable."),
        "risk": "low",
        "path": "~/.cache/thumbnails",
        "size_fn": lambda: dir_size("~/.cache/thumbnails"),
        "clean_fn": make_rm_contents_clean("~/.cache/thumbnails"),
    },
    # --- Language/runtime caches ---
    {
        "name": _("pip cache"),
        "desc": _("Python pip wheel download cache."),
        "risk": "low",
        "path": "~/.cache/pip",
        "size_fn": lambda: dir_size("~/.cache/pip"),
        "clean_fn": make_rm_contents_clean("~/.cache/pip"),
    },
    {
        "name": _("Yarn (v1) cache"),
        "desc": _("~/.cache/yarn — package cache."),
        "risk": "low",
        "path": "~/.cache/yarn",
        "size_fn": lambda: dir_size("~/.cache/yarn"),
        "clean_fn": make_rm_contents_clean("~/.cache/yarn"),
    },
    {
        "name": _("Yarn (Berry) cache"),
        "desc": _("~/.yarn/cache — package cache."),
        "risk": "low",
        "path": "~/.yarn/cache",
        "size_fn": lambda: dir_size("~/.yarn/cache"),
        "clean_fn": make_rm_contents_clean("~/.yarn/cache"),
    },
    {
        "name": _("Go module cache"),
        "desc": _("~/go/pkg/mod — `go clean -modcache` (files are read-only)."),
        "risk": "low",
        "path": "~/go/pkg/mod",
        "size_fn": lambda: dir_size("~/go/pkg/mod"),
        "clean_fn": make_cmd_clean(["go", "clean", "-modcache"]),
    },
    {
        "name": _("Cargo registry + git"),
        "desc": _("~/.cargo/registry and ~/.cargo/git — Rust crate cache."),
        "risk": "low",
        "path": "~/.cargo/{registry,git}",
        "size_fn": lambda: dir_size("~/.cargo/registry") + dir_size("~/.cargo/git"),
        "clean_fn": lambda: _clean_multi(["~/.cargo/registry", "~/.cargo/git"]),
    },
    {
        "name": _("Conda package cache"),
        "desc": _("`conda clean --all` (if available)."),
        "risk": "low",
        "path": "Conda pkgs",
        "size_fn": lambda: dir_size("~/miniconda3/pkgs") + dir_size("~/anaconda3/pkgs"),
        "clean_fn": make_cmd_clean(["conda", "clean", "--all", "-y"]),
    },
    # --- ML / model caches (medium — expensive to re-download) ---
    {
        "name": _("Hugging Face cache"),
        "desc": _("~/.cache/huggingface — downloaded models. Will be re-downloaded."),
        "risk": "medium",
        "path": "~/.cache/huggingface",
        "size_fn": lambda: dir_size("~/.cache/huggingface"),
        "clean_fn": make_rm_contents_clean("~/.cache/huggingface"),
    },
    {
        "name": _("PyTorch hub cache"),
        "desc": _("~/.cache/torch — model checkpoints."),
        "risk": "medium",
        "path": "~/.cache/torch",
        "size_fn": lambda: dir_size("~/.cache/torch"),
        "clean_fn": make_rm_contents_clean("~/.cache/torch"),
    },
    {
        "name": _("TensorFlow cache"),
        "desc": _("~/.cache/tensorflow — saved models."),
        "risk": "medium",
        "path": "~/.cache/tensorflow",
        "size_fn": lambda: dir_size("~/.cache/tensorflow"),
        "clean_fn": make_rm_contents_clean("~/.cache/tensorflow"),
    },
    # --- IDE / Editor caches ---
    {
        "name": _("JetBrains cache"),
        "desc": _("~/.cache/JetBrains — IntelliJ/PyCharm/WebStorm etc."),
        "risk": "low",
        "path": "~/.cache/JetBrains",
        "size_fn": lambda: dir_size("~/.cache/JetBrains"),
        "clean_fn": make_rm_contents_clean("~/.cache/JetBrains"),
    },
    {
        "name": _("VS Code (config) cache"),
        "desc": _("~/.config/Code/Cache + CachedData — extension/session cache."),
        "risk": "low",
        "path": "~/.config/Code/Cache*",
        "size_fn": lambda: dir_size("~/.config/Code/Cache") + dir_size("~/.config/Code/CachedData"),
        "clean_fn": lambda: _clean_multi(["~/.config/Code/Cache", "~/.config/Code/CachedData"]),
    },
    # --- Messaging/media caches ---
    {
        "name": _("Slack cache"),
        "desc": _("~/.config/Slack/Cache — will be re-downloaded."),
        "risk": "low",
        "path": "~/.config/Slack/Cache",
        "size_fn": lambda: dir_size("~/.config/Slack/Cache"),
        "clean_fn": make_rm_contents_clean("~/.config/Slack/Cache"),
    },
    {
        "name": _("Discord cache"),
        "desc": "~/.config/discord/Cache",
        "risk": "low",
        "path": "~/.config/discord/Cache",
        "size_fn": lambda: dir_size("~/.config/discord/Cache"),
        "clean_fn": make_rm_contents_clean("~/.config/discord/Cache"),
    },
    {
        "name": _("Spotify cache"),
        "desc": _("~/.cache/spotify — local media cache."),
        "risk": "low",
        "path": "~/.cache/spotify",
        "size_fn": lambda: dir_size("~/.cache/spotify"),
        "clean_fn": make_rm_contents_clean("~/.cache/spotify"),
    },
    # --- Additional browser caches ---
    {
        "name": _("Firefox cache2 (all profiles)"),
        "desc": _("~/.mozilla/firefox/*/cache2 — disk cache."),
        "risk": "low",
        "path": "~/.mozilla/firefox/*/cache2",
        "size_fn": size_firefox_cache,
        "clean_fn": lambda: clean_firefox_cache(),
    },
    # --- System side ---
    {
        "name": _("System crash dumps"),
        "desc": _("/var/crash + /var/lib/systemd/coredump — requires root."),
        "risk": "low",
        "path": "/var/crash, /var/lib/systemd/coredump",
        "size_fn": lambda: dir_size("/var/crash") + dir_size("/var/lib/systemd/coredump"),
        "clean_fn": make_cmd_clean(
            # Static glob expansion — no user input. shell=True required for
            # wildcard expansion under pkexec.
            "rm -rf /var/crash/* /var/lib/systemd/coredump/*",
            shell=True,
            need_root=True,  # nosec B602: vetted static command
        ),
    },
    {
        "name": _("Old kernel packages"),
        "desc": _(
            "Purges linux-image/headers/modules packages except the current "
            "and the previous one (apt purge, root)."
        ),
        "risk": "medium",
        "path": "linux-image-*, linux-headers-*",
        "size_fn": size_old_kernels,
        "clean_fn": clean_old_kernels,
    },
]

# Include user-defined rules
SYSTEM_TASKS.extend(load_user_cleaners())


__all__ = [
    "SYSTEM_TASKS",
    "load_user_cleaners",
    "make_app_uninstall_tasks",
    "make_artifact_tasks",
    "make_cmd_clean",
    "make_duplicate_tasks",
    "make_empty_tasks",
    "make_folder_explorer_tasks",
    "make_old_files_tasks",
    "make_rm_contents_clean",
    "make_rm_path_clean",
    "make_similar_image_tasks",
]
