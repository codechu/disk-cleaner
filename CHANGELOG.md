# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Internationalization (i18n) via gettext.** Source code transitioned
  to English; Turkish (`tr.po`) shipped as translation. UI auto-detects
  via `LANG` / `LC_MESSAGES`; explicit override with
  `DISK_CLEANER_LANG=tr`. ~270 user-facing strings wrapped with `_()`.
  Adding new languages: `cd po && msginit -i messages.pot -l <lang>`.
- Packaging: `packaging/debian/` (control, rules, changelog,
  copyright, install) for Launchpad PPA upload.
- Packaging: `packaging/AppImage/build.sh` (linuxdeploy + gtk + python
  plugin) and `.github/workflows/appimage.yml` for tag-triggered
  AppImage releases.
- Branding: new master icon `assets/icon/disk-cleaner.svg` (disk +
  treemap quadrant metaphor) + monochrome symbolic 16px variant.
- Marketing: `assets/social-preview.svg` (1280×640 GitHub social
  card), `docs/PRESS_KIT.md` (channel-specific copy variants),
  `docs/VERSIONING.md` (SemVer policy + release process),
  `assets/screenshots/README.md` (capture playbook).

### Changed
- Refactor: progressively extracted legacy module into focused packages
  (core, scanners, cleaners, viz, ui, api, watchdog). Public API stable.

## [0.1.0] — 2026-05-18

### Added
- First open-source release.
- Modular Python package `disk_cleaner/` with documented extension
  points (`Scanner`, `Cleaner`, `VizStrategy`).
- Smart suggestion panel with process-aware scoring and reasons.
- Interactive treemap and sunburst with hover, click-to-zoom,
  breadcrumb navigation, drill animations, dark-mode palette.
- Background watchdog (detached, PID-guarded) with desktop
  notifications.
- Control API on `/tmp/disk_cleaner_$(id -u).sock` (JSON-line).
- Headless CLI: `--scan`, `--clean`, `--dry-run`, JSON / CSV / table.
- User-defined cleaners via JSON files under
  `~/.config/disk_cleaner/cleaners/`.
- Persistent SQLite caches: `du_cache.db` (430× faster re-scan) and
  `snapshots.db` (7-day growth).
- `pyproject.toml`, MIT license, EN + TR README, CONTRIBUTING,
  DESIGN_PRINCIPLES, docs (ARCHITECTURE, API, CLI, SCANNERS,
  CLEANER_RULES), GitHub Actions CI, desktop / AppData metadata.

### Security
- Trash mode (`gio trash`) is the default for destructive operations.
- Dry-run honored everywhere.
- The control-API `clean` path is **blocked** by design — only the GUI
  can perform destructive operations.
- Active-project protection: git mtime within 30 days excludes a
  project from automatic selection.
- User data paths (Documents, Pictures, workspace…) are excluded from
  auto-clean.

[Unreleased]: https://github.com/codechu/disk-cleaner/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/codechu/disk-cleaner/releases/tag/v0.1.0
