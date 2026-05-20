# Architecture

## Package layout

```
disk_cleaner/
├── __init__.py            # version + main/cli_main re-export
├── __main__.py            # python -m disk_cleaner
├── _bus.py                # application-level codechu-events Bus singleton
├── _gtk.py                # single gi.require_version site
├── _tasks.py              # SYSTEM_TASKS + make_*_tasks factories
├── app.py                 # AppContext (composition root)
├── cli.py                 # console entry + main() (uses codechu-cli widgets)
├── config.py              # codechu-xdg App + path constants
├── errors.py              # DiskCleanerError hierarchy
├── runtime.py             # TRASH_MODE / DRY_RUN (UI ↔ core channel)
├── settings.py            # SETTINGS + SettingsStore
├── theme.py               # dark/light theme detection
├── utils.py               # run, human, parse_size, ThrottledProgress
│
├── core/                  # UI-independent, pure logic (testable)
│   ├── apps.py            # dpkg-query → installed apps
│   ├── kernels.py         # old kernel packages
│   ├── process.py         # OpenPathsCache (lsof)
│   ├── safe_remove.py     # gio trash + fallback
│   ├── score.py           # compute_score_and_reason
│   ├── sizing.py          # dir_size / path_size / sparse detection
│   ├── system_helpers.py  # docker / apt / journal / snap / firefox
│   └── walker.py          # find_project_artifacts / duplicates / empty
│
├── storage/
│   ├── du_cache.py        # SQLite mtime cache (~430× faster re-scan)
│   └── snapshots.py       # 7-day growth analysis snapshot store
│
├── scanners/              # STRATEGY — Scanner ABC + 9 implementations
├── cleaners/              # STRATEGY — Cleaner ABC + 3 implementations
├── viz/                   # STRATEGY — VizStrategy (treemap + sunburst)
├── controllers/           # Presenter (View-independent state machine)
│   ├── main.py            # MainController (mount/trash/dry/watchdog)
│   ├── suggestion.py      # SuggestionController (score + group + auto-select)
│   ├── task_list.py       # TaskListController (scan/select/clean)
│   └── treemap.py         # TreemapController (drill state)
├── ui/                    # Platform ports
│   └── gtk/               # Linux GTK 3
├── api/                   # Unix socket control server
└── watchdog/              # detached background daemon
```

## Presenter / Controller layer

The UI's business logic is **separate from the View**. Each panel is
backed by a controller:

- :class:`~disk_cleaner.controllers.MainController` — mount list,
  disk usage parsing, trash/dry runtime toggles, watchdog
- :class:`~disk_cleaner.controllers.SuggestionController` — score + group
  + auto-select + target picker + blacklist + growth
- :class:`~disk_cleaner.controllers.TaskListController` — scan/select/
  clean + preview thread + confirmation flow
- :class:`~disk_cleaner.controllers.TreemapController` — drill stack +
  viz mode + path persistence

Contract:

- Controllers **never import GTK/Qt/HTML** — they can be tested headlessly
  under pytest.
- The View listens to state changes via the observer pattern;
  ``on_busy_changed``, ``on_rows_replaced``, and similar callable attributes.
- Callbacks may arrive from worker threads; the View marshals them onto
  its UI thread with ``GLib.idle_add`` (GTK) or
  ``QMetaObject.invokeMethod`` (Qt).
- Animations, hover state, and widget-specific concerns stay in the View.

Adding a new platform port (Qt, Web, Textual) therefore **does not
require rewriting the business logic** — only widget glue and observer
bindings.

## Composition root

`AppContext` (`disk_cleaner/app.py`) wires every dependency in one place.
The UI and API request services through this object instead of reaching
into module globals.

```python
ctx = AppContext()
ctx.settings.get("trash_mode", True)
size = ctx.du_cache.get("~/.cache")
growth = ctx.snapshots.growth(items)
holders = ctx.open_paths.holders("/path")
scanner = ctx.scanner("system")
```

## Strategy pattern

Three main open/closed surfaces: Scanner, Cleaner, VizStrategy.

- **Scanner** — `list_tasks(*, cancel, progress) -> Iterable[Task]`
  produces Tasks for a scannable source (system cache, project artifacts,
  old files, duplicates, …). 9 built-ins.
- **Cleaner** — `execute() -> (returncode, message)` performs a single
  cleanup operation. SafePath / Contents / Command (3 built-ins).
- **VizStrategy** — `layout`, `hit_test`, `draw`. Treemap and Sunburst
  implement the same interface; the UI swaps strategies when tabs change.

To add a new scan or visualization, see [SCANNERS.md](SCANNERS.md).

## Runtime state channel

`disk_cleaner/runtime.py` exposes two mutable globals:

- `TRASH_MODE` — Trash mode (toggled by a UI checkbox).
- `DRY_RUN` — Test mode (commands are not executed, just logged).

The UI writes them, and lower-level modules (`cleaners.command`,
`core.safe_remove`, `core.system_helpers`, `core.kernels`, `_tasks`) read
them at call time (late binding → no import-order issues). They may
later move into `SettingsStore` as typed accessors.

## codechu-* library dependencies (v0.2 migration)

As of v0.2.x, the previously-inlined helpers have been extracted into
standalone PyPI packages under the `codechu-*` namespace and declared in
`pyproject.toml`:

| Package          | Used for                                                          |
|------------------|-------------------------------------------------------------------|
| `codechu-events` | `Bus` — controller/panel/API event fan-out                        |
| `codechu-xdg`    | `App(vendor, product, env, uid)` — XDG-compliant path layout      |
| `codechu-cli`    | `Color`, `ProgressLine`, `Spinner`, `banner`, `confirm`, `multiselect`, `resolve_format`, `format_examples`, `capabilities` |
| `codechu-treeviz`| `build_tree`, `layout_treemap`, `node_color` — treemap geometry  |

The remaining helpers (`codechu-fmt`, `codechu-meter`, `codechu-spark`)
are released but not yet wired up here; do not add imports against them
without declaring the dependency in `pyproject.toml` first.

### Application-level event Bus singleton

`disk_cleaner/_bus.py` constructs a single `Bus` and re-exports it:

```python
from disk_cleaner._bus import bus
bus.emit("scan.started", panel="suggestion")
```

`codechu-events` 0.2 dropped module-level shims; library-level singletons
are forbidden by the library's design principle. An **application**-level
singleton is appropriate because every controller, panel, and
control-socket subscriber in this product shares one event topology. The
indirection lives in this module so tests can swap the bus when needed.

### codechu-xdg App composition

`disk_cleaner/config.py` constructs an `App(vendor, product, env, uid)`
once at import time:

```python
_env = default_env()
_uid = os.getuid()
_app = App(vendor="codechu", product="disk-cleaner", env=_env, uid=_uid)

SETTINGS_FILE  = _app.settings_file("settings.json")
DU_CACHE_DB    = _app.cache_file("du_cache.db")
SNAPSHOTS_DB   = _app.data_file("snapshots.db")
WATCHDOG_PID   = _app.runtime_file("watchdog.pid")
CONTROL_SOCKET = str(_app.runtime_file("control.sock"))
```

All paths land under the shared `codechu/disk-cleaner/` namespace inside
the appropriate XDG base directory. `migrate_pre_xdg_layout()` ports
both the pre-v0.1 flat layout and the v0.1 XDG-but-vendorless layout
into the v0.2 location.

### codechu-cli usage (CLI surface)

`disk_cleaner/cli.py` builds its interactive surface from the
`codechu-cli` widget set:

- `Color(stream, enabled=...)` — fluent themed coloring (`.high`,
  `.medium`, `.low`, `.bold`, `.dim`)
- `ProgressLine` — single-line streaming scan progress
- `Spinner` — context manager around long blocking probes (e.g. `lsof`)
- `multiselect` — source picker + cleanup picker
- `confirm` — pre-delete prompt with safe defaults
- `banner` — headline output for `--scan` / `--clean`
- `capabilities`, `resolve_format`, `format_examples` — TTY detection,
  format auto-pick, help epilog example formatting

See [CLI.md](CLI.md) for the user-facing flags and flows these power.

## Backward-compatibility contract

The following are **stable**:

- `python3 disk_cleaner.py …` (legacy entry, runs through a shim)
- `python3 -m disk_cleaner …` and the `disk-cleaner` console script
- CLI flags (`--scan`, `--clean`, `--dry-run`, `--watchdog-*`, …)
- Control API command names
- `~/.config/disk_cleaner/settings.json` keys
- `du_cache.db` and `snapshots.db` schemas
- `watchdog.pid` format
- `cleaners/*.json` schema
