"""CLI dispatch + ``main()`` entry point.

Arguments are parsed via argparse; ``--scan``/``--clean``/
``--watchdog-*``/``--snapshot``/``--set``/etc. run headless,
invocation without flags starts the GTK GUI.

Legacy entry points (``python3 disk_cleaner.py``,
``python -m disk_cleaner``, ``disk-cleaner``) all flow through here.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from codechu_cli import (
    Color,
    ProgressLine,
    banner,
    confirm,
    format_examples,
    resolve_format,
)

from . import __version__
from ._gtk import Gtk
from .config import HOME, SETTINGS_FILE, SNAPSHOTS_DB, USER_CLEANERS_DIR
from .core.process import get_open_paths
from .core.score import compute_score_and_reason
from .i18n import _, ngettext
from .utils import human
from .watchdog.daemon import (
    WATCHDOG_PID_FILE,
    watchdog_loop,
    watchdog_running,
    watchdog_start_background,
    watchdog_stop,
)

# Known settings keys for --set/--get/--list-settings.
# Dotted keys are stored as nested JSON.
_KNOWN_SETTINGS: dict[str, dict] = {
    "language": {"choices": ("en", "tr"), "type": "str"},
    "theme": {"choices": ("auto", "light", "dark"), "type": "str"},
    "viz_mode": {"choices": ("treemap", "sunburst"), "type": "str"},
    "watchdog.threshold": {"type": "size"},
    "watchdog.interval": {"type": "int"},
}


def cli_collect_tasks(
    sources: set[str],
    workspace: str | None = None,
    downloads: str | None = None,
    progress: bool = True,
) -> list[dict]:
    """``sources``: subset of ``"system"``, ``"artifacts"``, ``"oldfiles"``.

    Returns a list of dicts enriched with score and reason, sorted by
    size descending. The ``_task`` key must be filtered out before
    writing to the output.

    When ``progress`` is truthy and stderr is a TTY, prints a live
    per-task progress line to stderr so the user sees activity during
    long scans. Stdout (the JSON/CSV/table payload) is never touched.
    """
    from ._tasks import (
        SYSTEM_TASKS,
        make_artifact_tasks,
        make_old_files_tasks,
    )

    pl = ProgressLine(stream=sys.stderr, enabled=(progress and sys.stderr.isatty()))
    state = {"done": 0, "total": 0, "bytes": 0}

    def _redraw(label: str) -> None:
        msg = "  [{done}/{total}] {bytes} · {label}".format(
            done=state["done"],
            total=state["total"],
            bytes=human(state["bytes"]),
            label=label,
        )
        pl.update(msg)

    def _sized(t: dict, kind: str) -> tuple[dict, int] | None:
        label = t.get("name") or t.get("path") or "?"
        _redraw(_("scanning {kind} · {label}…").format(kind=kind, label=label))
        try:
            size = t["size_fn"]() or 0
        except Exception:
            size = 0
        state["done"] += 1
        state["bytes"] += size
        _redraw(_("scanned {kind} · {label} — {size}").format(
            kind=kind, label=label, size=human(size),
        ))
        return (t, size) if size > 0 else None

    open_paths = get_open_paths()
    results: list[tuple[dict, int, str]] = []
    if "system" in sources:
        state["total"] += len(SYSTEM_TASKS)
        for t in SYSTEM_TASKS:
            r = _sized(t, "system")
            if r:
                results.append((r[0], r[1], "system"))
    if "artifacts" in sources:
        ws = Path(workspace or (HOME / "workspace"))
        if ws.exists():
            tasks = list(make_artifact_tasks(str(ws)))
            state["total"] += len(tasks)
            for t in tasks:
                r = _sized(t, "artifact")
                if r:
                    results.append((r[0], r[1], "artifact"))
    if "oldfiles" in sources:
        d = Path(downloads or (HOME / "İndirilenler"))
        if not d.exists():
            d = HOME / "Downloads"
        if d.exists():
            tasks = list(make_old_files_tasks(str(d), 90))
            state["total"] += len(tasks)
            for t in tasks:
                r = _sized(t, "oldfile")
                if r:
                    results.append((r[0], r[1], "oldfile"))

    pl.clear()
    enriched: list[dict] = []
    for t, size, kind in results:
        score, reason = compute_score_and_reason(t, size, kind, open_paths)
        enriched.append(
            {
                "name": t.get("name", ""),
                "path": t.get("path", ""),
                "kind": kind,
                "size_bytes": size,
                "size_human": human(size),
                "score": int(score),
                "reason": reason,
                "risk": t.get("risk", ""),
                "_task": t,  # internal — stripped from output
            }
        )
    enriched.sort(key=lambda x: -x["score"])
    return enriched


# ---------- Settings helpers ----------


def _parse_size(s: str) -> int:
    """Parse a size string like '5G', '500M', '1024' into bytes.

    Accepts B/K/M/G/T suffix (case-insensitive). Raises ValueError on
    malformed input — the caller should surface a friendly error.
    """
    s = s.strip()
    if not s:
        raise ValueError("empty size")
    units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    suffix = s[-1].upper()
    if suffix in units:
        return int(float(s[:-1]) * units[suffix])
    return int(s)


def _load_settings_json() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_settings_json(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _settings_get(data: dict, key: str):
    if "." in key:
        head, tail = key.split(".", 1)
        return _settings_get(data.get(head, {}) or {}, tail)
    return data.get(key)


def _settings_set(data: dict, key: str, value) -> None:
    if "." in key:
        head, tail = key.split(".", 1)
        if head not in data or not isinstance(data.get(head), dict):
            data[head] = {}
        _settings_set(data[head], tail, value)
    else:
        data[key] = value


def _validate_and_coerce(key: str, raw_value: str):
    spec = _KNOWN_SETTINGS[key]
    t = spec["type"]
    if t == "str":
        if "choices" in spec and raw_value not in spec["choices"]:
            raise ValueError(
                f"value must be one of: {', '.join(spec['choices'])}"
            )
        return raw_value
    if t == "int":
        try:
            return int(raw_value)
        except ValueError as e:
            raise ValueError(f"expected integer, got {raw_value!r}") from e
    if t == "size":
        try:
            _parse_size(raw_value)
        except ValueError as e:
            raise ValueError(f"expected size like '5G', got {raw_value!r}") from e
        # Persist the original human-readable string (matches GUI convention)
        return raw_value
    return raw_value


def _cmd_set(arg: str) -> int:
    if "=" not in arg:
        print(_("error: --set requires KEY=VALUE"), file=sys.stderr)
        return 2
    key, _sep, value = arg.partition("=")
    key = key.strip()
    if key not in _KNOWN_SETTINGS:
        print(
            _("error: unknown key {key!r}. Known keys: {keys}").format(
                key=key, keys=", ".join(sorted(_KNOWN_SETTINGS)),
            ),
            file=sys.stderr,
        )
        return 2
    try:
        coerced = _validate_and_coerce(key, value)
    except ValueError as e:
        print(_("error: {msg}").format(msg=str(e)), file=sys.stderr)
        return 2
    data = _load_settings_json()
    _settings_set(data, key, coerced)
    try:
        _save_settings_json(data)
    except Exception as e:
        print(_("error: failed to write settings: {msg}").format(msg=e), file=sys.stderr)
        return 1
    print(f"set {key}={value}", file=sys.stderr)
    return 0


def _cmd_get(key: str) -> int:
    if key not in _KNOWN_SETTINGS:
        print(
            _("error: unknown key {key!r}. Known keys: {keys}").format(
                key=key, keys=", ".join(sorted(_KNOWN_SETTINGS)),
            ),
            file=sys.stderr,
        )
        return 2
    data = _load_settings_json()
    val = _settings_get(data, key)
    if val is None:
        return 1
    print(val)
    return 0


def _cmd_list_settings() -> int:
    data = _load_settings_json()
    width = max(len(k) for k in _KNOWN_SETTINGS)
    for k in sorted(_KNOWN_SETTINGS):
        v = _settings_get(data, k)
        print(f"{k.ljust(width)}  {('' if v is None else v)}")
    return 0


# ---------- Custom cleaner management ----------


def _cleaner_paths_dir() -> Path:
    USER_CLEANERS_DIR.mkdir(parents=True, exist_ok=True)
    return USER_CLEANERS_DIR


def _cmd_list_cleaners() -> int:
    d = _cleaner_paths_dir()
    files = sorted(d.glob("*.json"))
    if not files:
        print(_("No custom cleaners installed."))
        return 0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"{f.stem}\t{f}\t(invalid: {e})", file=sys.stderr)
            continue
        name = data.get("name") or f.stem
        # The user-rule schema uses "paths" + optional "command".
        paths = data.get("paths") or []
        path_field = ", ".join(paths) if paths else (
            " ".join(data["command"]) if isinstance(data.get("command"), list)
            else (data.get("command") or "")
        )
        desc = data.get("desc") or data.get("description") or ""
        print(f"{name}\t{path_field}\t{desc}")
    return 0


def _cmd_add_cleaner(path: str, *, force: bool = False) -> int:
    src = Path(path).expanduser()
    if not src.is_file():
        print(_("error: file not found: {p}").format(p=src), file=sys.stderr)
        return 1
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception as e:
        print(_("error: invalid JSON: {msg}").format(msg=e), file=sys.stderr)
        return 1
    # Schema validation matches disk_cleaner._tasks.load_user_cleaners().
    # Required: "name". At least one of "paths" or "command" must be present
    # so the rule actually does something.
    name = data.get("name")
    if not name or not isinstance(name, str):
        print(_("error: cleaner JSON must have a non-empty 'name'"), file=sys.stderr)
        return 1
    if not data.get("paths") and not data.get("command"):
        print(
            _("error: cleaner JSON must have at least one of 'paths' or 'command'"),
            file=sys.stderr,
        )
        return 1
    risk = data.get("risk", "medium")
    if risk not in ("low", "medium", "high"):
        print(
            _("error: 'risk' must be one of: low, medium, high (got {r!r})").format(r=risk),
            file=sys.stderr,
        )
        return 1
    # Safe filename — strip path separators from the rule name.
    safe = name.replace("/", "_").replace("\\", "_")
    dest = _cleaner_paths_dir() / f"{safe}.json"
    if dest.exists() and not force:
        print(
            _("error: {p} exists. Use --force to overwrite.").format(p=dest),
            file=sys.stderr,
        )
        return 1
    shutil.copyfile(src, dest)
    print(_("installed: {p}").format(p=dest), file=sys.stderr)
    return 0


def _cmd_remove_cleaner(name: str) -> int:
    target = _cleaner_paths_dir() / f"{name}.json"
    if not target.exists():
        print(_("error: no cleaner named {n!r}").format(n=name), file=sys.stderr)
        return 1
    target.unlink()
    print(_("removed: {p}").format(p=target), file=sys.stderr)
    return 0


# ---------- Snapshot CLI ----------


def _cmd_snapshot(args_list: list[str]) -> int:
    if not args_list:
        print(_("error: --snapshot requires a subaction: create|list|diff"), file=sys.stderr)
        return 2
    sub = args_list[0]
    rest = args_list[1:]
    if sub == "create":
        from ._tasks import SYSTEM_TASKS
        from .storage.snapshots import save_snapshot

        items = []
        open_paths = get_open_paths()
        for t in SYSTEM_TASKS:
            try:
                size = t["size_fn"]() or 0
            except Exception:
                size = 0
            if size <= 0:
                continue
            score, _reason = compute_score_and_reason(t, size, "system", open_paths)
            items.append(
                {
                    "path": t.get("path", ""),
                    "kind": "system",
                    "size_bytes": size,
                    "score": int(score),
                    "risk": t.get("risk", ""),
                }
            )
        sid = save_snapshot(items)
        if sid is None:
            print(_("error: failed to save snapshot"), file=sys.stderr)
            return 1
        print(sid)
        return 0
    if sub == "list":
        import sqlite3

        if not SNAPSHOTS_DB.exists():
            print(_("No snapshots."), file=sys.stderr)
            return 0
        conn = sqlite3.connect(str(SNAPSHOTS_DB))
        try:
            cur = conn.execute(
                "SELECT id, scanned_at, total_size, item_count "
                "FROM snapshots ORDER BY scanned_at DESC"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        if not rows:
            print(_("No snapshots."), file=sys.stderr)
            return 0
        for sid, ts, total, count in rows:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
            print(f"{sid}\t{stamp}\t{human(int(total or 0))}\t{int(count or 0)}")
        return 0
    if sub == "diff":
        # Accept either two positional ids or a single "A:B" form.
        if len(rest) == 1 and ":" in rest[0]:
            a_s, b_s = rest[0].split(":", 1)
        elif len(rest) == 2:
            a_s, b_s = rest
        else:
            print(_("error: --snapshot diff requires A B (or A:B)"), file=sys.stderr)
            return 2
        try:
            a, b = int(a_s), int(b_s)
        except ValueError:
            print(_("error: snapshot ids must be integers"), file=sys.stderr)
            return 2
        from .storage.snapshots import snapshot_items

        a_items = snapshot_items(a)
        b_items = snapshot_items(b)
        if not a_items and not b_items:
            print(_("error: no items found for snapshots {a} and {b}").format(a=a, b=b),
                  file=sys.stderr)
            return 1
        paths = sorted(set(a_items) | set(b_items))
        for p in paths:
            sa = a_items.get(p, 0)
            sb = b_items.get(p, 0)
            delta = sb - sa
            if delta == 0 and sa and sb:
                continue
            if sa == 0:
                tag = "+"
            elif sb == 0:
                tag = "-"
            else:
                tag = "~"
            sign = "+" if delta >= 0 else "-"
            print(f"{tag}\t{sign}{human(abs(delta))}\t{human(sa)} -> {human(sb)}\t{p}")
        return 0
    print(_("error: unknown --snapshot subaction {s!r}").format(s=sub), file=sys.stderr)
    return 2


# ---------- Treemap export ----------


def export_treemap_png(
    root_path: str,
    out_path: str,
    width: int = 1600,
    height: int = 1000,
) -> int:
    """Render a treemap of ``root_path`` to a PNG at ``out_path``.

    Returns 0 on success, non-zero on failure. cairo is a runtime
    dep already required by the GTK UI.
    """
    try:
        import cairo  # noqa: F401  — checked early so we can surface a clear error
        from codechu_treeviz import build_tree, layout_treemap, node_color
    except Exception as e:
        print(
            _("error: treemap export requires cairo + codechu_treeviz: {msg}").format(msg=e),
            file=sys.stderr,
        )
        return 2

    root = build_tree(root_path)
    if root is None:
        print(_("error: path not readable: {p}").format(p=root_path), file=sys.stderr)
        return 1
    layout_treemap(root, 0, 0, float(width), float(height))

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surf)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()

    def draw(node, top_idx: int, depth: int) -> None:
        if node.rect is None:
            return
        x, y, w, h = node.rect
        if w < 1 or h < 1:
            return
        r, g, b = node_color(
            top_idx, depth, dark=False, is_other=getattr(node, "is_other", False),
        )
        cr.set_source_rgb(r, g, b)
        cr.rectangle(x, y, w, h)
        cr.fill()
        cr.set_source_rgba(0, 0, 0, 0.3)
        cr.set_line_width(0.5)
        cr.rectangle(x, y, w, h)
        cr.stroke()
        if w > 60 and h > 16:
            cr.set_source_rgb(0.1, 0.1, 0.1)
            cr.select_font_face("sans-serif")
            cr.set_font_size(min(14.0, h * 0.4))
            cr.move_to(x + 4, y + 14)
            base = os.path.basename(node.path) or node.path
            if getattr(node, "is_other", False):
                label = f"(other ×{getattr(node, 'small_count', 0)})"
            else:
                label = base
            cr.show_text(label[: max(8, int(w / 8))])
        for i, child in enumerate(node.children):
            draw(child, top_idx if depth > 0 else i, depth + 1)

    for i, child in enumerate(root.children):
        draw(child, i, 1)
    try:
        surf.write_to_png(out_path)
    except Exception as e:
        print(_("error: failed to write {p}: {msg}").format(p=out_path, msg=e),
              file=sys.stderr)
        return 1
    return 0


# ---------- argparse ----------


def _build_parser() -> argparse.ArgumentParser:
    epilog = format_examples([
        ("disk-cleaner --scan", _("Smart scan with table output")),
        ("disk-cleaner --scan > scan.json", _("Headless JSON for scripts")),
        ("disk-cleaner --clean --items 'Chrome cache,pip cache'",
         _("Clean only the named items")),
        ("disk-cleaner --clean --dry-run", _("Preview the clean")),
        ("disk-cleaner --watchdog-start && disk-cleaner --watchdog-status",
         _("Start watchdog + check status")),
        ("disk-cleaner --set language=tr", _("Change a setting")),
        ("disk-cleaner --snapshot create && disk-cleaner --snapshot list",
         _("Take + list snapshots")),
        ("disk-cleaner --export-treemap ~/Downloads -o /tmp/dl.png",
         _("Headless treemap PNG")),
    ])
    p = argparse.ArgumentParser(
        prog="disk_cleaner",
        description=_("Disk Cleaner — GUI or CLI"),
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "-V", "--version", action="version",
        version=f"Disk Cleaner v{__version__} (codechu/disk-cleaner)",
    )
    p.add_argument(
        "--scan", action="store_true", help=_("Headless scan, prints result (default: json)")
    )
    p.add_argument("--clean", action="store_true", help=_("Scan and clean low-risk + safe items"))
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=_("Do not delete anything, only show what would be done"),
    )
    p.add_argument(
        "-y", "--yes", action="store_true",
        help=_("Assume yes; do not prompt for confirmation on --clean"),
    )
    p.add_argument(
        "--items",
        help=_("Only clean tasks whose name is in this comma-separated list"),
    )
    p.add_argument(
        "--trash",
        dest="trash",
        action="store_true",
        default=None,
        help=_("Trash mode (default on)"),
    )
    p.add_argument("--no-trash", dest="trash", action="store_false", help=_("Permanent delete"))
    p.add_argument(
        "--format",
        choices=["json", "csv", "table"],
        default=None,
        help=_(
            "Output format (with --scan). Default: table when stdout is "
            "a terminal, json when redirected or piped."
        ),
    )
    p.add_argument(
        "--sources",
        default="system,artifacts,oldfiles",
        help=_("Sources (comma-separated): system,artifacts,oldfiles"),
    )
    p.add_argument("--workspace", help=_("Root path for artifact scan"))
    p.add_argument("--downloads", help=_("Root path for old-files scan"))
    p.add_argument(
        "--min-score",
        type=int,
        default=40,
        help=_("Minimum score threshold for auto cleanup (default 40)"),
    )
    p.add_argument(
        "--watchdog", action="store_true", help=_("Run in background watchdog mode (infinite loop)")
    )
    p.add_argument(
        "--watchdog-start", action="store_true", help=_("Start watchdog in the background (detach)")
    )
    p.add_argument("--watchdog-stop", action="store_true", help=_("Stop running watchdog"))
    p.add_argument("--watchdog-status", action="store_true", help=_("Print watchdog status"))

    # Settings
    p.add_argument("--set", metavar="KEY=VALUE", help=_("Update a setting"))
    p.add_argument("--get", metavar="KEY", help=_("Print a setting's value"))
    p.add_argument("--list-settings", action="store_true", help=_("List all known settings"))

    # Custom cleaners
    p.add_argument("--list-cleaners", action="store_true", help=_("List installed custom cleaners"))
    p.add_argument("--add-cleaner", metavar="PATH", help=_("Install a cleaner JSON file"))
    p.add_argument("--remove-cleaner", metavar="NAME", help=_("Remove an installed cleaner"))
    p.add_argument(
        "--force", action="store_true",
        help=_("Overwrite when --add-cleaner conflicts with an existing rule"),
    )

    # Snapshots
    p.add_argument(
        "--snapshot", nargs="+", metavar="SUBACTION",
        help=_("Snapshot subcommand: create | list | diff A B"),
    )

    # Treemap export
    p.add_argument(
        "--export-treemap", metavar="PATH",
        help=_("Render a treemap PNG for the given path"),
    )
    p.add_argument(
        "-o", "--output", metavar="FILE",
        help=_("Output file (used with --export-treemap)"),
    )
    return p


def _selected_exclusive_count(args: argparse.Namespace) -> int:
    """How many mutually-exclusive top-level actions are selected?"""
    flags = [
        bool(args.scan),
        bool(args.clean),
        bool(args.watchdog),
        bool(args.watchdog_start),
        bool(args.watchdog_stop),
        bool(args.watchdog_status),
        args.set is not None,
        args.get is not None,
        bool(args.list_settings),
        bool(args.list_cleaners),
        args.add_cleaner is not None,
        args.remove_cleaner is not None,
        args.snapshot is not None,
        args.export_treemap is not None,
    ]
    return sum(1 for f in flags if f)


def cli_main(argv: list[str]) -> int:
    """Headless CLI dispatcher."""
    from . import runtime

    p = _build_parser()
    args = p.parse_args(argv)

    # Interactive banner — single source of truth for "headline" output
    # that lets the user confirm they're in the right tool/mode at a glance.
    if sys.stderr.isatty() and (args.scan or args.clean):
        if args.dry_run:
            mode = "dry-run"
        elif args.clean:
            mode = "clean"
        else:
            mode = "scan"
        banner("Disk Cleaner", f"v{__version__}", mode=mode)

    # Settings / cleaners / snapshot / export — each short-circuits so
    # they never trigger a scan or watchdog operation.
    if args.set is not None:
        return _cmd_set(args.set)
    if args.get is not None:
        return _cmd_get(args.get)
    if args.list_settings:
        return _cmd_list_settings()
    if args.list_cleaners:
        return _cmd_list_cleaners()
    if args.add_cleaner is not None:
        return _cmd_add_cleaner(args.add_cleaner, force=args.force)
    if args.remove_cleaner is not None:
        return _cmd_remove_cleaner(args.remove_cleaner)
    if args.snapshot is not None:
        return _cmd_snapshot(args.snapshot)
    if args.export_treemap is not None:
        if not args.output:
            print(_("error: --export-treemap requires -o OUTPUT"), file=sys.stderr)
            return 2
        return export_treemap_png(args.export_treemap, args.output)

    if args.watchdog:
        try:
            WATCHDOG_PID_FILE.write_text(str(os.getpid()))
        except Exception:
            pass
        try:
            watchdog_loop()
        finally:
            try:
                WATCHDOG_PID_FILE.unlink()
            except OSError:
                pass
        return 0
    if args.watchdog_start:
        if watchdog_start_background():
            print(_("watchdog started"))
            return 0
        print(_("watchdog is already running"))
        return 1
    if args.watchdog_stop:
        if watchdog_stop():
            print(_("watchdog stopped"))
            return 0
        # Not running is a normal observable state, not a failure.
        print(_("watchdog is not running"))
        return 0
    if args.watchdog_status:
        if watchdog_running():
            pid = WATCHDOG_PID_FILE.read_text().strip()
            print(_("watchdog RUNNING (pid {pid})").format(pid=pid))
            return 0
        # STOPPED is a normal observable state, not a failure.
        print(_("watchdog STOPPED"))
        return 0

    if args.dry_run:
        runtime.DRY_RUN = True
    if args.trash is not None:
        runtime.TRASH_MODE = args.trash

    if not (args.scan or args.clean):
        p.print_help()
        return 0

    sources = {s.strip() for s in args.sources.split(",") if s.strip()}
    scan_t0 = time.monotonic()
    enriched = cli_collect_tasks(sources, workspace=args.workspace, downloads=args.downloads)
    scan_elapsed = time.monotonic() - scan_t0

    if args.clean:
        if args.items:
            # Selective clean — bypass score/risk filter. The user has
            # explicitly named what they want; respect them.
            wanted = [n.strip() for n in args.items.split(",") if n.strip()]
            by_name = {r["name"]: r for r in enriched}
            targets = []
            for name in wanted:
                hit = by_name.get(name)
                if hit is None:
                    # Some cleaners prefix with an emoji ("👤 X"); allow
                    # suffix match so users don't have to copy emojis.
                    matches = [r for r in enriched if r["name"].endswith(name)]
                    if len(matches) == 1:
                        hit = matches[0]
                if hit is None:
                    print(
                        _("warning: no task named {n!r}, skipping").format(n=name),
                        file=sys.stderr,
                    )
                    continue
                targets.append(hit)
            if not targets:
                print(
                    _("error: none of the requested items matched a known task"),
                    file=sys.stderr,
                )
                return 2
        else:
            # Low risk + above score threshold + not active + not currently open
            targets = [
                r
                for r in enriched
                if r["risk"] == "low"
                and r["score"] >= args.min_score
                and "ACTIVE" not in (r.get("reason", "") + r.get("name", ""))
                and "currently open" not in r.get("reason", "")
            ]
        total = sum(r["size_bytes"] for r in targets)
        if runtime.DRY_RUN:
            mode = _("DRY-RUN")
        elif runtime.TRASH_MODE:
            mode = _("trash")
        else:
            mode = _("PERMANENT")
        count_msg = ngettext(
            "{n} item, ~{size} ({mode})",
            "{n} items, ~{size} ({mode})",
            len(targets),
        ).format(n=len(targets), size=human(total), mode=mode)
        print(f"# {count_msg}", file=sys.stderr)

        # Confirmation gate — skip for --dry-run (read-only), respect
        # -y/--yes, and short-circuit when stderr is not a TTY (CI/pipe).
        if not runtime.DRY_RUN and targets:
            c = Color(sys.stderr)
            if runtime.TRASH_MODE:
                prompt = _("Proceed? Will trash {n} items, {size} total.").format(
                    n=len(targets), size=human(total),
                )
            else:
                prompt = c.high(_("Proceed? Will PERMANENTLY DELETE {n} items, {size} total.").format(
                    n=len(targets), size=human(total),
                ))
            if not confirm(prompt, default=False, assume_yes=args.yes):
                print(_("Aborted."), file=sys.stderr)
                return 1

        ok = 0
        for r in targets:
            t = r["_task"]
            try:
                rc, out = t["clean_fn"]()
            except Exception as e:
                rc, _out = 1, str(e)
            status = _("OK") if rc == 0 else _("FAIL")
            print(f"[{status}] {r['name']}  {r['size_human']}", file=sys.stderr)
            if rc == 0:
                ok += 1
        print(
            "# " + _("{ok}/{total} successful").format(ok=ok, total=len(targets)),
            file=sys.stderr,
        )
        return 0 if ok == len(targets) else 1

    # --scan: output. Format defaults to a human-readable table when
    # stdout is a TTY (interactive use) and to json when stdout is
    # redirected to a file or pipe (machine consumption). Explicit
    # --format overrides this.
    fmt = args.format or resolve_format(sys.stdout, tty_default="table", pipe_default="json")

    output_items = [{k: v for k, v in r.items() if not k.startswith("_")} for r in enriched]
    total_bytes = sum(r["size_bytes"] for r in output_items)
    total_human = human(total_bytes)

    if fmt == "json":
        json.dump(
            {
                "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "items": output_items,
                "totals": {
                    "count": len(output_items),
                    "size_bytes": total_bytes,
                    "size_human": total_human,
                },
            },
            sys.stdout,
            indent=2,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    elif fmt == "csv":
        import csv

        w = csv.DictWriter(
            sys.stdout,
            fieldnames=[
                "name",
                "path",
                "kind",
                "size_bytes",
                "size_human",
                "score",
                "reason",
                "risk",
            ],
        )
        w.writeheader()
        for r in output_items:
            w.writerow(r)
    else:  # table
        TABLE_LIMIT = 20
        n_total = len(output_items)
        c = Color(sys.stdout)
        if n_total == 0:
            print(_("No items found in the selected sources. Nothing to do."))
        else:
            print(
                _("Found {n} item(s), {total} total. Top {shown} by score:").format(
                    n=c.bold(str(n_total)),
                    total=c.bold(total_human),
                    shown=min(TABLE_LIMIT, n_total),
                )
            )
            print()
            for r in output_items[:TABLE_LIMIT]:
                risk_color = r["risk"] if r["risk"] in ("low", "medium", "high") else "dim"
                risk_render = getattr(c, risk_color)(r["risk"])
                print(
                    f"{r['score']:>3}  {r['size_human']:>8}  "
                    f"{risk_render:<16}  {r['name']}   "
                    f"{c.dim('──')} {c.dim(r['reason'])}"
                )
            if n_total > TABLE_LIMIT:
                extra = n_total - TABLE_LIMIT
                print()
                print(
                    c.dim(
                        ngettext(
                            "… and {n} more item. Run with --format json for the full list.",
                            "… and {n} more items. Run with --format json for the full list.",
                            extra,
                        ).format(n=extra),
                    )
                )

    if sys.stderr.isatty():
        print(
            _("Scan complete: {n} items, {total} total, {secs:.1f}s.").format(
                n=len(output_items), total=total_human, secs=scan_elapsed,
            ),
            file=sys.stderr,
        )
    return 0


def main() -> None:
    """Program main entry — GUI or CLI depending on arguments."""
    # Set program class deterministically so GNOME shell can match the
    # running window back to packaging/disk-cleaner.desktop's
    # StartupWMClass and show the correct icon in the taskbar/launcher.
    # This must happen before GTK is initialized (i.e. before MainWindow).
    from gi.repository import GLib

    GLib.set_prgname("codechu-disk-cleaner")

    # Prepare XDG directories + migrate legacy (pre-XDG) layout if present
    from .config import ensure_dirs, migrate_pre_xdg_layout

    migrate_pre_xdg_layout()
    ensure_dirs()

    cli_args = [a for a in sys.argv[1:] if a.startswith("-")]
    if cli_args:
        try:
            sys.exit(cli_main(sys.argv[1:]))
        except KeyboardInterrupt:
            # Standard SIGINT exit code; no traceback. Match the message
            # to the lifecycle stage we were in (already announced via
            # the progress lines in cli_collect_tasks).
            print(_("\nCancelled by user."), file=sys.stderr, flush=True)
            sys.exit(130)

    # GUI path — make Ctrl-C in the launching terminal close the window
    # cleanly instead of dumping a Python traceback. The SIGINT handler
    # schedules Gtk.main_quit on the main thread (signals can arrive on
    # any thread; idle_add is thread-safe).
    import signal

    def _on_sigint(_signo: int, _frame) -> None:  # noqa: ANN001
        print(_("\nClosing window…"), file=sys.stderr, flush=True)
        GLib.idle_add(Gtk.main_quit)

    signal.signal(signal.SIGINT, _on_sigint)

    from .theme import apply_user_preference
    from .ui import MainWindow

    apply_user_preference()  # SETTINGS.theme → GTK dark-mode hint
    win = MainWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    try:
        Gtk.main()
    except KeyboardInterrupt:
        # Shouldn't happen — our SIGINT handler above intercepts —
        # but cover the path defensively.
        print(_("\nClosing window…"), file=sys.stderr, flush=True)
        sys.exit(130)


def cli_entry() -> None:
    """``disk-cleaner`` console entry point (pyproject scripts hook)."""
    cli_main(sys.argv[1:])


__all__ = ["cli_collect_tasks", "cli_main", "cli_entry", "export_treemap_png", "main"]
