# CLI Reference

`disk-cleaner [options]` or `python3 -m disk_cleaner [options]`.
When run without arguments, the GTK GUI starts.

## Flags

| Flag                       | Meaning                                                     |
|----------------------------|-------------------------------------------------------------|
| `--scan`                   | Headless scan, prints results (default: JSON)               |
| `--clean`                  | Scan + clean low-risk and safe items                        |
| `--dry-run`                | Don't delete anything; print what would be done             |
| `--trash`                  | Trash mode (ON by default)                                  |
| `--no-trash`               | Permanent deletion (use with care)                          |
| `--format {json,csv,table}`| `--scan` output format                                      |
| `--sources LIST`           | Comma-separated: `system,artifacts,oldfiles`                |
| `--workspace PATH`         | Root path for artifact scanning                             |
| `--downloads PATH`         | Root path for old-file scanning                             |
| `--min-score INT`          | Minimum score threshold for auto-clean (default 40)         |
| `--watchdog`               | Infinite watchdog loop (foreground)                         |
| `--watchdog-start`         | Detach the watchdog and start it in the background          |
| `--watchdog-stop`          | Stop a running watchdog                                     |
| `--watchdog-status`        | Print watchdog status                                       |

## Examples

```bash
# Scan system sources and show as a table
disk-cleaner --scan --sources system --format table

# List artifacts under the workspace as JSON
disk-cleaner --scan --sources artifacts --workspace ~/code --format json

# Clean everything low-risk, but first see what would be done
disk-cleaner --clean --dry-run --min-score 60

# Start the watchdog (free-space alerts)
disk-cleaner --watchdog-start
disk-cleaner --watchdog-status
disk-cleaner --watchdog-stop
```

## Output formats

- **json**: machine-friendly, fields `name`, `desc`, `risk`, `path`,
  `kind`, `size_bytes`, `score`, `reason`.
- **csv**: same fields, comma-separated.
- **table**: readable at a glance in the terminal, no colors.
