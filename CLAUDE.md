# CLAUDE.md — Disk Cleaner

If you are an AI agent invoked in this repo, **bootstrap first** per
the org rules:

1. Read `codechu-org/ai/AGENTS.md` §0 (Bootstrap) and §1–§7. Prefer
   the local clone at `$org_home/codechu-org/ai/AGENTS.md` if
   `~/.config/codechu/config.toml` has `org_home` set (employee
   setup); otherwise WebFetch the raw URL
   <https://raw.githubusercontent.com/codechu/codechu-org/main/ai/AGENTS.md>
   (public; works for external contributors).
2. Read this file (product-local overrides below).
3. If you have a clone of `codechu/codechu-internal` on this machine,
   read `ai/AGENTS.internal.md` — extends, never weakens, public
   rules. If not, you are an external contributor; do not invent
   internal context.
4. Skim [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
   [`docs/DESIGN_PRINCIPLES.md`](DESIGN_PRINCIPLES.md).
5. Summarize back in 3 bullets, wait for confirmation.

## Product-local notes

- GTK 3 + PyGObject + Cairo. Python 3.10+. Tests in `tests/` run
  without GTK (controllers + scanners are headless-safe).
- Run before "done": `ruff check . && pytest -q`. Both gate CI.
- The control API (`docs/API.md`) is reachable at
  `$XDG_RUNTIME_DIR/codechu/disk-cleaner/control.sock` when the GUI
  runs; useful for screenshot regen (`assets/screenshots/README.md`).
- Translations: edit only source English strings; never hand-edit
  `po/tr.po` directly — run `cd po && make update && make compile`.
- Vendor namespace: every path is `codechu/disk-cleaner/<...>`; the
  vendor constant lives in `disk_cleaner/config.py`.
- The 6 extracted libraries (`codechu-events`, `codechu-xdg`,
  `codechu-cli`, `codechu-fmt`, `codechu-meter`, `codechu-spark`) plus
  `codechu-treeviz` are declared dependencies in `pyproject.toml`:
  events / xdg / cli at `>=0.2,<0.3`, treeviz at `>=0.1,<0.2`. The
  application-level event bus singleton lives at
  `disk_cleaner/_bus.py`; controllers and the control-socket server
  import it as `from disk_cleaner._bus import bus`. XDG paths come
  from a module-level `App(vendor, product, env, uid)` in
  `disk_cleaner/config.py`.

## Discipline reminders (org rules apply)

- No AI signature in commits.
- No `--no-verify`, no `git push --force`, no destructive git without
  explicit per-action go-ahead.
- No speculative language in docs ("we will", "by v2.0 we plan").
- See `codechu-org/ai/AGENTS.md` for the full list.
