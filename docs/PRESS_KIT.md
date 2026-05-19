# Press Kit — Disk Cleaner

Ready-to-use marketing copy. Each channel has different character
limits; copy and paste the variant you need.

---

## 1. Project identity

| Field | Value |
|---|---|
| Name (official) | **Disk Cleaner** |
| Full name | **Codechu Disk Cleaner** |
| Vendor | Codechu |
| App ID (deb/AppImage/Snap) | `codechu-disk-cleaner` |
| App ID (Flatpak/AppStream) | `io.github.codechu.DiskCleaner` *(initial)* or `com.codechu.DiskCleaner` *(after domain verification)* |
| License | MIT |
| Repo | https://github.com/codechu/disk-cleaner |
| Homepage | https://codechu.com (planned) |
| Email | info@codechu.com |
| Brand color | `#1d4e83` (primary) · `#5da9e0` (accent) |

---

## 2. Tagline — 30–80 characters (store summaries)

| Length | Text | Usage |
|---|---|---|
| 30 ch | `Safe disk cleaner for Linux` | Snap Store summary (max ~79) |
| 50 ch | `Safe, transparent disk cleaner for Linux` | Flathub summary, .desktop GenericName |
| 79 ch | `Safe, transparent disk cleaner with smart suggestions and treemap view` | Full Snap Store summary |

**Turkish:**

| Length | Text |
|---|---|
| 30 ch | `Güvenli Linux disk temizleyici` |
| 50 ch | `Akıllı önerili, güvenli Linux disk temizleyici` |
| 79 ch | `Akıllı önerili, güvenli, şeffaf Linux disk temizleyici — treemap görünümlü` |

---

## 3. Short description — 200–300 characters

> Disk Cleaner is a Linux utility that helps you reclaim disk space safely. It scans your home and system, scores cleanup candidates with process-aware heuristics (it won't touch a cache your browser is actively using), and previews everything with an interactive treemap and sunburst.

**TR:**

> Disk Cleaner, Linux'ta disk alanını güvenle geri kazandırır. Ev klasörünü ve sistemi tarar, süreç-farkındalıklı önerilerle (tarayıcının kullandığı cache'lere dokunmadan) puanlar; interaktif treemap ve sunburst ile her şeyi önceden gösterir.

---

## 4. Long description — Flathub / AppData (400–800 words)

> **Disk Cleaner** is an open-source desktop utility for Linux that helps you reclaim disk space safely and transparently.
>
> **Smart, process-aware suggestions.** Instead of blindly deleting caches, Disk Cleaner inspects which files are currently held open by running processes (`lsof`) and excludes them. It scores candidates by age, size, and known cleanup-safe paths, then shows you a one-line reason for every item — no opaque "Clean now" button.
>
> **Interactive visualization.** A squarified treemap and a sunburst view let you explore any mount point. Click to zoom in, breadcrumb to zoom out, hover for size and path. Dark-mode palette by default.
>
> **Safety by design.** All destructive operations default to your trash folder (`gio trash`). Dry-run is honored everywhere. Active projects are auto-protected: any git working tree modified in the last 30 days is excluded. The control-API path is **deliberately blocked** from destructive operations — only the GUI window can perform cleanup, so a misbehaving script or IDE plugin cannot wipe files.
>
> **Background watchdog (opt-in).** A detached, single-instance daemon watches free space and notifies you when it drops below a threshold. It does nothing on its own — it just tells you.
>
> **Headless CLI + control API.** Run `disk-cleaner --scan --format json` from any script. Plug into automation through the Unix socket at `/tmp/disk_cleaner_$(id -u).sock`.
>
> **Extensible.** Drop a JSON file into `~/.config/disk_cleaner/cleaners/` and your custom cleanup rule appears in the UI alongside the built-in ones.
>
> Built with GTK 3 and Python 3.10+. No telemetry. MIT licensed.

---

## 5. Feature bullets — README / store listing

```
* Smart, process-aware suggestions (won't touch a cache your browser is using)
* Interactive squarified treemap + sunburst over any mount
* Trash mode by default + dry-run honored everywhere
* Background watchdog with low-space notifications (opt-in)
* Headless CLI: --scan, --clean, --dry-run, JSON/CSV/table
* Control API on Unix socket — destructive path blocked by design
* User-defined cleanup rules via JSON drop-in files
* Persistent SQLite caches: 430× faster re-scan, 7-day growth tracking
* Dark mode default, GTK 3, no telemetry
```

---

## 6. Keywords / tags

**Suggested GitHub Topics** (up to 20):

```
disk-cleaner  linux  gtk  python  treemap  sunburst  disk-usage
filesystem  cleanup  cache  systemd  appindicator  visualization
gnome  ubuntu  open-source  cli  desktop-application  mit-license
disk-analyzer
```

**.desktop Keywords**: already set to `disk;cleaner;treemap;sunburst;cache;temizleyici;` — sufficient.

**AppStream `<keywords>` addition** (optional, appdata.xml):

```xml
<keywords>
  <keyword>disk</keyword>
  <keyword>cleaner</keyword>
  <keyword>storage</keyword>
  <keyword>treemap</keyword>
  <keyword>sunburst</keyword>
  <keyword>cache</keyword>
  <keyword>cleanup</keyword>
</keywords>
```

---

## 7. Social media / blog launch copy

### Twitter / X — 280 characters

> 🧹 Just released **Disk Cleaner** v0.1.0 — an open-source disk cleaner for Linux with smart, process-aware suggestions and an interactive treemap. Trash mode by default, control-API blocks destructive ops. MIT. github.com/codechu/disk-cleaner

### Hacker News — title (60 ch)

> Show HN: Disk Cleaner – process-aware Linux disk cleanup w/ treemap

### Reddit r/linux — title

> [Release] Disk Cleaner v0.1.0 — safe, transparent disk cleanup for Linux with treemap/sunburst, GTK 3, MIT

### Mastodon / Bluesky — 500 ch

> Released Disk Cleaner v0.1.0 today — a Linux disk cleaner that actually reads which files your apps have open before suggesting cleanup. Treemap + sunburst visualization, trash-by-default, control-API can't perform destructive ops (only GUI can). GTK 3, Python, MIT.
>
> github.com/codechu/disk-cleaner

### Blog post (Codechu) — title suggestions

- "Disk Cleaner: a safer way to reclaim Linux disk space"
- "Why your disk cleaner shouldn't trust itself — building a process-aware cleanup tool"
- "Disk Cleaner v0.1.0 — open source, GTK, treemap, no telemetry"

---

## 8. Store listing characteristics

### Flathub (`appdata.xml`)

- **Summary** (max 80 ch): the 50 ch variant above
- **Description**: Section 4 (long description)
- **Screenshots** (required): 3-4 images from `assets/screenshots/`
- **OARS rating**: empty `oars-1.1` content rating (no screen content)
- **Categories**: `System;Utility;FileTools;` *(from .desktop)*

### Snap Store

- **Title**: `Disk Cleaner`
- **Summary** (max 79): the 79 ch variant above
- **Description**: Section 4
- **License**: `MIT`
- **Contact**: `info@codechu.com`
- **Website**: `https://github.com/codechu/disk-cleaner` (update once codechu.com is live)
- **Categories**: `Utilities` / `System`

### Launchpad PPA (apt) — not needed

apt metadata is read from the `debian/control` Description field. Already written.

### AppImageHub

A single-line URL: `https://github.com/codechu/disk-cleaner` — the rest is pulled automatically from release tags.

---

## 9. Screenshots & demo

Not captured yet — see `assets/screenshots/README.md`. They must be
captured **before** the v0.1.0 release (the Flathub validator rejects
submissions without them).

Demo GIF / video (optional but strong):

- 10-15 s, the suggestion → click → preview → clean flow
- Capture with `peek` or `byzanz-record`
- Keep the GIF under 1.5 MB (so it loads quickly when embedded in the README)
- Place it at the top of the README

---

## 10. Quick pre-release checklist

- [ ] Final icon — `assets/icon/disk-cleaner.svg` *(✅ done)*
- [ ] Social preview — `assets/social-preview.svg` → upload to GitHub Settings *(SVG ready; convert to PNG)*
- [ ] Screenshots 1280×720 *(❗ missing — capture guide: `assets/screenshots/README.md`)*
- [ ] GitHub repo description set
- [ ] GitHub topics set (Section 6)
- [ ] Codechu org logo / avatar
- [ ] README hero image
- [ ] CHANGELOG.md up to date
- [ ] v0.1.0 tag + GitHub Release notes
- [ ] info@codechu.com reachable
