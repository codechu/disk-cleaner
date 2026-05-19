"""CLI dispatch + ``main()`` entry point.

Arguments are parsed via argparse; ``--scan``/``--clean``/
``--watchdog-*`` are headless mode, invocation without arguments starts
the GTK GUI.

Legacy entry points (``python3 disk_cleaner.py``,
``python -m disk_cleaner``, ``disk-cleaner``) all flow through here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from ._gtk import Gtk
from .config import HOME
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

    show_progress = progress and sys.stderr.isatty()

    def _sized(t: dict, kind: str) -> tuple[dict, int] | None:
        if show_progress:
            label = t.get("name") or t.get("path") or "?"
            t0 = time.monotonic()
            print(f"  scanning [{kind}] {label}…", end="", file=sys.stderr, flush=True)
        try:
            size = t["size_fn"]() or 0
        except Exception:
            size = 0
        if show_progress:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            # Overwrite the in-progress line with the final result.
            print(f"\r  scanned  [{kind}] {label} — {human(size)} ({elapsed_ms}ms)",
                  file=sys.stderr, flush=True)
        return (t, size) if size > 0 else None

    open_paths = get_open_paths()
    results: list[tuple[dict, int, str]] = []
    if "system" in sources:
        if show_progress:
            print(f"# {len(SYSTEM_TASKS)} system tasks", file=sys.stderr, flush=True)
        for t in SYSTEM_TASKS:
            r = _sized(t, "system")
            if r:
                results.append((r[0], r[1], "system"))
    if "artifacts" in sources:
        from pathlib import Path

        ws = Path(workspace or (HOME / "workspace"))
        if ws.exists():
            tasks = list(make_artifact_tasks(str(ws)))
            if show_progress:
                print(f"# {len(tasks)} artifact tasks under {ws}", file=sys.stderr, flush=True)
            for t in tasks:
                r = _sized(t, "artifact")
                if r:
                    results.append((r[0], r[1], "artifact"))
    if "oldfiles" in sources:
        from pathlib import Path

        d = Path(downloads or (HOME / "İndirilenler"))
        if not d.exists():
            d = HOME / "Downloads"
        if d.exists():
            tasks = list(make_old_files_tasks(str(d), 90))
            if show_progress:
                print(f"# {len(tasks)} old-file tasks under {d}", file=sys.stderr, flush=True)
            for t in tasks:
                r = _sized(t, "oldfile")
                if r:
                    results.append((r[0], r[1], "oldfile"))
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


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="disk_cleaner",
        description=_("Disk Cleaner — GUI or CLI"),
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
        default="json",
        help=_("Output format (with --scan)"),
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
    return p


def cli_main(argv: list[str]) -> int:
    """Headless CLI dispatcher."""
    from . import runtime

    p = _build_parser()
    args = p.parse_args(argv)

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
        print(_("watchdog is not running"))
        return 1
    if args.watchdog_status:
        if watchdog_running():
            pid = WATCHDOG_PID_FILE.read_text().strip()
            print(_("watchdog RUNNING (pid {pid})").format(pid=pid))
            return 0
        print(_("watchdog STOPPED"))
        return 1

    if args.dry_run:
        runtime.DRY_RUN = True
    if args.trash is not None:
        runtime.TRASH_MODE = args.trash

    if not (args.scan or args.clean):
        p.print_help()
        return 0

    sources = {s.strip() for s in args.sources.split(",") if s.strip()}
    enriched = cli_collect_tasks(sources, workspace=args.workspace, downloads=args.downloads)

    if args.clean:
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

    # --scan: output
    output_items = [{k: v for k, v in r.items() if not k.startswith("_")} for r in enriched]
    if args.format == "json":
        json.dump(
            {
                "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "items": output_items,
                "totals": {
                    "count": len(output_items),
                    "size_bytes": sum(r["size_bytes"] for r in output_items),
                    "size_human": human(sum(r["size_bytes"] for r in output_items)),
                },
            },
            sys.stdout,
            indent=2,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    elif args.format == "csv":
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
        for r in output_items[:50]:
            print(
                f"{r['score']:>3}  {r['size_human']:>8}  "
                f"{r['risk']:<7}  {r['name']}   ── {r['reason']}"
            )
        if len(output_items) > 50:
            extra = len(output_items) - 50
            print(
                ngettext(
                    "… and {n} more item",
                    "… and {n} more items",
                    extra,
                ).format(n=extra)
            )
    return 0


def main() -> None:
    """Program main entry — GUI or CLI depending on arguments."""
    # Prepare XDG directories + migrate legacy (pre-XDG) layout if present
    from .config import ensure_dirs, migrate_pre_xdg_layout

    migrate_pre_xdg_layout()
    ensure_dirs()

    cli_args = [a for a in sys.argv[1:] if a.startswith("-")]
    if cli_args:
        sys.exit(cli_main(sys.argv[1:]))
    from .theme import apply_user_preference
    from .ui import MainWindow

    apply_user_preference()  # SETTINGS.theme → GTK dark-mode hint
    win = MainWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


def cli_entry() -> None:
    """``disk-cleaner`` console entry point (pyproject scripts hook)."""
    cli_main(sys.argv[1:])


__all__ = ["cli_collect_tasks", "cli_main", "cli_entry", "main"]
