# Disk Cleaner — Brand identity

Brand identity guide. Logo system, color palette, typography, and usage
rules. Every marketing artifact is derived from this document.

## 1. Logo system

### Core glyph
**G3 Spotlight** — disk plate (radial gradient navy) + white "D" letter +
circular counter (spindle area) + gold spindle hub.

The mark carries no literal meaning; it is purely the brand signature.
Meaning is delivered by the wordmark. This follows the Notion / Linear /
Vercel approach.

### Files — [assets/logo/](../assets/logo/)

| File | Usage |
|---|---|
| `mark.svg` | Full-color brand glyph (200×200 viewBox) |
| `mark-knockout.svg` | On dark backgrounds — white disk, dark D, gold hub |
| `mark-mono.svg` | Single color — adapts to GTK theme via currentColor |
| `wordmark.svg` | Just the "Disk Cleaner" typography |
| `lockup-horizontal.svg` | Mark + wordmark side by side (primary lockup) |
| `lockup-stacked.svg` | Mark on top, wordmark below (store listings, etc.) |

### App icon — [assets/icon/](../assets/icon/)

| File | Size |
|---|---|
| `disk-cleaner.svg` | 128 viewBox master, infinitely scalable |
| `disk-cleaner-symbolic.svg` | 16px monochrome GTK tray |

The master is rendered to 16/24/32/48/64/128/256/512/1024 PNGs. The
command lives in [`assets/icon/README.md`](../assets/icon/README.md).

## 2. Color palette

### Primary — Navy
| Token | Hex | Usage |
|---|---|---|
| `--brand-navy-light` | `#34507a` | Disk gradient highlight (top-left) |
| `--brand-navy` | `#1d2939` | Primary brand color (D, wordmark, UI) |
| `--brand-navy-dark` | `#0f1928` | Disk gradient shadow (bottom-right) |

### Accent — Gold
| Token | Hex | Usage |
|---|---|---|
| `--brand-gold` | `#e0a020` | Spindle hub, small accents |

### Neutrals
| Token | Hex | Usage |
|---|---|---|
| `--brand-paper` | `#fafaf7` | Off-white background, D letter |
| `--brand-ink` | `#1d2939` | Body text (same as navy) |

### Color ratio rule
- Navy family: **80%** of any composition
- Paper (off-white): **15%**
- Gold: **5%** — accent only (logo hub, link highlight, badge)

Gold is never used as a large area color; only as a small attention
point.

## 3. Typography

### Primary — Ubuntu Sans (or Inter / system-ui fallback)
- **Display / headline:** weight 600-700, letter-spacing -1.5 to -2
- **Body / paragraph:** weight 400-500, letter-spacing 0
- **Caption / meta:** weight 400, opacity 0.55-0.70

CSS / SVG font-family stack:
```css
font-family: "Ubuntu Sans", "Inter", system-ui, -apple-system, sans-serif;
```

### Secondary — JetBrains Mono (code, terminal, technical)
- Code blocks
- CLI banners
- Command examples

### Hierarchy example
| Element | Size | Weight | Tracking |
|---|---|---|---|
| Hero headline | 92px | 700 | -2 |
| Section heading | 48px | 600 | -1.5 |
| Body | 16-18px | 400 | 0 |
| Caption | 14px | 400 | 0.5 |
| Meta / mono | 14px | 500 | 0 |

## 4. Logo usage rules

### Safe zone
Leave **one disk radius** of empty space around the mark (r=78 → 78px
on every edge).

### Minimum size
- **Mark only:** 16px (favicon threshold)
- **Horizontal lockup:** 120px wide minimum
- **Stacked lockup:** 100px wide minimum

### Don't
- ❌ **Rotate** the logo (skew, flip)
- ❌ Change the color palette (e.g., green hub instead of gold)
- ❌ **Flatten the gradient** of the master (use the mono variant for that)
- ❌ Typeset the wordmark in **another typeface**
- ❌ Add **extra elements** inside the mark (tagline, version, etc.)
- ❌ Place the mark **inside a frame** (it already has a circular plate)

### Do
- ✅ White / light background: `mark.svg` (full-color)
- ✅ Dark background: `mark-knockout.svg`
- ✅ Single-color print / GTK symbolic: `mark-mono.svg`
- ✅ As an app icon: `assets/icon/disk-cleaner.svg`
- ✅ Web meta og:image: `assets/social-preview.svg`

## 5. Tone of voice

Character:
- **Calm + precise** — no over-promising, factual
- **Process-aware** — the product's defining trait
- **OSS-native** — terminal-friendly, dev-respecting
- **No marketing fluff** — avoid words like "revolutionary" and "best-in-class"

Standard tagline: **"Process-aware. Trash-by-default. Treemap + sunburst."**

For longer descriptions see [PRESS_KIT.md](PRESS_KIT.md).

## 6. File organization

```
assets/
├─ logo/
│  ├─ mark.svg                       # primary mark
│  ├─ mark-knockout.svg              # dark bg
│  ├─ mark-mono.svg                  # single-color
│  ├─ wordmark.svg                   # text only
│  ├─ lockup-horizontal.svg          # mark + text horizontal
│  └─ lockup-stacked.svg             # mark + text vertical
├─ icon/
│  ├─ disk-cleaner.svg               # app icon master
│  └─ disk-cleaner-symbolic.svg      # GTK 16px mono
├─ screenshots/                      # used in README + appdata
└─ social-preview.svg                # 1280×640 og:image

packaging/
└─ icon.svg                          # kept in sync with master (copy)
```

## 7. Output / production commands

PNG render (before every release):
```bash
python3 -c "
import gi; gi.require_version('Rsvg','2.0')
from gi.repository import Rsvg
import cairo
for src, sizes in [
    ('assets/icon/disk-cleaner.svg', [16,24,32,48,64,128,256,512,1024]),
    ('assets/social-preview.svg', [(1280,640)]),
]:
    h = Rsvg.Handle.new_from_file(src)
    d = h.get_dimensions()
    for sz in sizes:
        w,hh = (sz,sz) if isinstance(sz,int) else sz
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, hh)
        c = cairo.Context(s); c.scale(w/d.width, hh/d.height); h.render_cairo(c)
        s.write_to_png(src.replace('.svg', f'-{w}.png' if w==hh else f'-{w}x{hh}.png'))
"
```

## 8. Brand evolution

Current: **v4** (G3 Spotlight, D-letter mark). This document reflects
current usage; iteration history and rationale live in the publisher
archive.
