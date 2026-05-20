# CLI Reference

`disk-cleaner [options]` or `python3 -m disk_cleaner [options]`.
When run without arguments, the GTK GUI starts.

## Flags

### Actions

| Flag                       | Meaning                                                     |
|----------------------------|-------------------------------------------------------------|
| `--scan`                   | Headless scan, prints results (default: table on TTY, json piped) |
| `--clean`                  | Scan + clean low-risk and safe items                        |
| `--dry-run`                | Don't delete anything; print what would be done             |
| `-y`, `--yes`              | Skip confirmation prompt on `--clean`                       |
| `--items LIST`             | Selective clean — only tasks whose name is in this list     |
| `--trash`                  | Trash mode (ON by default)                                  |
| `--no-trash`               | Permanent deletion (use with care)                          |
| `--format {json,csv,table}`| `--scan` output format (auto-detected if omitted)           |
| `--sources LIST`           | Comma-separated: `system,artifacts,oldfiles`                |
| `--workspace PATH`         | Root path for artifact scanning                             |
| `--downloads PATH`         | Root path for old-file scanning                             |
| `--min-score INT`          | Minimum score threshold for auto-clean (default 40)         |

### Interactive UX

| Flag                       | Meaning                                                     |
|----------------------------|-------------------------------------------------------------|
| `--no-color`               | Disable ANSI colors even on a TTY                           |
| `--no-progress`            | Disable progress lines + spinners even on a TTY             |
| `--non-interactive`        | Script mode — implies `--yes --no-progress --no-color`, defaults `--format=json`, never prompts |
| `--interactive-clean`      | After `--scan`, pick items to clean via multiselect (TTY only) |

### Watchdog / settings / misc

| Flag                       | Meaning                                                     |
|----------------------------|-------------------------------------------------------------|
| `--watchdog`               | Infinite watchdog loop (foreground)                         |
| `--watchdog-start`         | Detach the watchdog and start it in the background          |
| `--watchdog-stop`          | Stop a running watchdog                                     |
| `--watchdog-status`        | Print watchdog status (colored badge: ● RUNNING / ● STOPPED)|
| `--set KEY=VALUE`          | Update a setting                                            |
| `--get KEY`                | Print a setting's value                                     |
| `--list-settings`          | List known settings + current values                        |
| `--list-cleaners`          | List installed custom cleaners                              |
| `--add-cleaner PATH`       | Install a cleaner JSON file (`--force` to overwrite)        |
| `--remove-cleaner NAME`    | Remove an installed cleaner                                 |
| `--snapshot SUB ...`       | `create` \| `list` \| `diff A B` (or `A:B`)                 |
| `--export-treemap PATH -o FILE` | Render a treemap PNG headlessly                        |
| `-V`, `--version`          | Print version and exit                                      |

## Interactive flows

When stdout and stderr are both TTYs and `--non-interactive` is not set,
the CLI engages a few light-weight interactive flows backed by
`codechu-cli`:

- **Source picker.** When `--sources` is omitted, a multiselect lets you
  pick from `system`, `artifacts`, `oldfiles` (all three default-on).
- **Spinner.** While probing open file handles (`lsof`) at scan start,
  a single-line spinner shows progress on stderr.
- **Progress line.** Per-task `[done/total] bytes · label` line on stderr
  during scan (suppressed by `--no-progress` or when stderr is not a TTY).
- **Cleanup multiselect.** When `--scan --clean` are used together (or
  with `--interactive-clean`) on a TTY without explicit `--items`, the
  auto-selected target set is presented as a multiselect so you can trim
  it before deletion.
- **Confirmation.** Before any actual delete (skipped for `--dry-run`,
  `--yes`, and non-TTY). The trash-mode prompt is neutral; the permanent
  delete prompt is rendered in the high-risk color.
- **Colored helpers.** Error / warning / ok messages on stderr use the
  same Color theme (`_err` / `_warn` / `_ok` internal helpers).

## Safety guards

- `--non-interactive --clean` **without** both `--items` and an explicit
  `--sources` is refused (exit code **2**) — mass-delete with no
  constraints is a footgun in script mode.
- Confirmation prompts default to **no**.
- Trash mode (`gio trash`) is on by default; `--no-trash` is required for
  permanent deletion.

## Examples

```bash
# Interactive smart scan (table on TTY)
disk-cleaner --scan

# Headless JSON for scripts / CI
disk-cleaner --non-interactive --scan --sources system --format json

# List artifacts under a custom workspace as JSON
disk-cleaner --scan --sources artifacts --workspace ~/code --format json

# Preview a clean (no deletes, no prompts)
disk-cleaner --clean --dry-run --min-score 60

# Scan + pick targets interactively, then clean
disk-cleaner --scan --clean

# Clean only specific items by name (script-safe)
disk-cleaner --non-interactive --clean --items 'Chrome cache,pip cache'

# Watchdog lifecycle
disk-cleaner --watchdog-start
disk-cleaner --watchdog-status   # ● RUNNING (pid 12345)
disk-cleaner --watchdog-stop
```

## Output formats

- **json**: machine-friendly, fields `name`, `desc`, `risk`, `path`,
  `kind`, `size_bytes`, `size_human`, `score`, `reason`. Wrapped in a
  document with `scanned_at` + `totals`.
- **csv**: same fields, comma-separated.
- **table**: colored, readable at a glance; top 20 items by score
  followed by an "… and N more" footer when truncated.

The default format is auto-detected: `table` when stdout is a TTY,
`json` when stdout is redirected or piped. `--non-interactive` forces
`json`.
