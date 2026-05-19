# Custom Cleaner Rules

You don't need to write code to add a new cleaner to the Disk Cleaner
UI. Drop a JSON file under `~/.config/disk_cleaner/cleaners/` and
restart the app — it will be listed in the UI.

## Schema

```json
{
  "name": "Pacman cache (custom)",
  "desc": "Pacman cache — re-downloadable.",
  "risk": "low",
  "paths": ["/var/cache/pacman/pkg"],
  "command": null
}
```

### Fields

| Field     | Type    | Required | Meaning                                                  |
|-----------|---------|----------|----------------------------------------------------------|
| `name`    | string  | yes      | Short name shown in the UI                               |
| `desc`    | string  | yes      | One-line description (the user reads this)              |
| `risk`    | string  | yes      | `"low"`, `"medium"`, or `"high"`                        |
| `paths`   | string[]| no*      | Directory/file paths to delete (contents go to trash)    |
| `command` | string  | no*      | Shell command to run (absolute path recommended)         |

\* At **least one** of `paths` and `command` must be provided. If both
are present, `command` runs first, then `paths` are cleaned.

### Risk levels

- **low** — reversible / cache; does not affect your session or
  credentials.
- **medium** — affects context (e.g. Docker containers); user
  confirmation is recommended.
- **high** — what gets deleted is not easily recoverable; the UI shows
  an extra warning.

## Examples

### Path-only deletion

```json
{
  "name": "Yarn berry cache",
  "desc": "Yarn 2+ global cache. First installs will be slower.",
  "risk": "low",
  "paths": ["~/.yarn/berry/cache"]
}
```

### Command + path

```json
{
  "name": "pnpm store prune",
  "desc": "Run `pnpm store prune` and clean the remaining directory.",
  "risk": "low",
  "command": "pnpm store prune",
  "paths": ["~/.local/share/pnpm"]
}
```

## Safety

- **Absolute paths / `~` tilde** are accepted.
- `..` or glob (`*`) are passed through unresolved; if needed, make
  sure `paths` contains a single literal path.
- `command` is not executed via `subprocess.run(shell=True)` directly;
  it is parsed as an argv list. If you need a complex pipeline,
  consider writing a scanner instead.
- Trash mode is ON by default — `paths` go to the trash.
