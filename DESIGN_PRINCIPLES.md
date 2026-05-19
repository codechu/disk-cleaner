# Design Principles

This file distills the principles from `REFACTOR_PLAN.md` and serves as
the reference for keeping PRs aligned with the project. English is the
canonical language for this document.

## Architecture

- **DRY** — Extract repeating patterns into a base class / factory / helper.
- **SoC** — One responsibility per module: UI ≠ Domain ≠ Storage ≠ IPC.
- **DI** — Pass dependencies through the constructor; the `AppContext`
  composition root wires them in one place. New code does not use global state.
- **Strategy** — `Scanner`, `Cleaner`, `VizStrategy` are open-closed: a new
  behavior means a new class, not changes to existing code.
- **Composition > Inheritance** — Combine small parts; avoid deep
  inheritance hierarchies.
- **Explicit > Implicit** — No magic behavior; pass arguments, read the code.

## Security

- **Safety first** — Destructive operations go to the trash by default,
  after manual confirmation.
- **No destructive operations via the API** — The `clean` command is
  BLOCKED over the socket; only the user can trigger it from the GUI.
- **Dry-run** support — Destructive operations can be simulated first.
- **Active project protection** — Based on git mtime; excluded from auto-selection.
- **User-data exclusion** — Documents, Pictures, Videos, Music,
  Desktop, and workspace are outside the default scope of automatic cleanup.

## User experience

- **Progressive disclosure** — Complexity is hidden by default; revealed
  via an expander or "?" popover.
- **One-click assistant** — "Smart scan → conservative auto-selection →
  single Clean".
- **Reversibility** — Trash is the default; restorable from a standard
  file manager.
- **Visual hierarchy** — Primary action stands out, secondary is plain,
  destructive demands awareness.
- **Empty state** — Every panel shows an inviting message.
- **User-friendly error messages** — Technical detail to the log, a
  short summary to the user.
- **First-class dark mode** — Sat ~0.4 calm palette, soft hover.

## Code quality

- **Type hints required** — `from __future__ import annotations`, full
  annotations on the public API.
- **Docstrings** — Module + class + public function (short, "why"-focused).
- **Logging > print** — `logger = logging.getLogger(__name__)`.
- **Errors as classes** — `DiskCleanerError` base + specific subclasses.
- **Constants in one place** — `disk_cleaner/config.py`; no magic numbers.
- **i18n hooks ready** — `_("…")`-style wrapper in a future release.

## Test and CI

- Smoke tests — package import, --help, dry-run flow.
- Unit tests — pure logic (score, sizing, parsing, layout).
- Mock filesystem — real I/O via `tmp_path`.
- CI — ruff + pytest, GitHub Actions, Python 3.10/3.11/3.12.
- Backwards compatibility — settings.json, snapshot DB, and the control
  API protocol do not break.

## Performance

- **Cache** — `du` is heavy; SQLite mtime cache makes re-scan ~430× faster.
- **Background I/O** — All long-running work happens on a thread; the UI never freezes.
- **Cancel** — Long operations are interruptible via `cancel_event`.
- **Throttled progress** — 5 updates per second; doesn't drown the UI.
- **Lazy** — Treemap deep walk is on-demand, updated on hover.
