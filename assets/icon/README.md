# Icons — Codechu Disk Cleaner

Brand-distinctive metaphor: **disk platter with a treemap quadrant** —
references the app's signature visualization — plus a sweep highlight
(cleaning motion) and a sparkle (freed space).

## Files

| Dosya | Boyut | Kullanım |
|---|---|---|
| `disk-cleaner.svg` | 128×128 viewBox, scales to ∞ | Master kaynak, paketleyiciler |
| `disk-cleaner-symbolic.svg` | 16×16 monokrom | GTK tray / status-area; runtime'da renklenir |

`packaging/icon.svg` master'ın kopyasıdır (debian/AppImage/Flatpak buradan kopyalar). Master değiştiğinde:

```bash
cp assets/icon/disk-cleaner.svg packaging/icon.svg
```

## PNG üretimi (her release'den önce)

`hicolor` theme + Snap/Flatpak/AppImage genelde SVG kabul eder, ama **GitHub social preview**, **AppImageHub thumbnail** ve bazı eski platformlar PNG ister. Inkscape veya rsvg-convert ile:

```bash
# Tek seferlik — rsvg-convert (librsvg2-bin paketi)
for size in 16 24 32 48 64 128 256 512 1024; do
  rsvg-convert -w $size -h $size \
    assets/icon/disk-cleaner.svg \
    -o assets/icon/disk-cleaner-${size}.png
done

# Symbolic 16px (sadece bu boyut)
rsvg-convert -w 16 -h 16 \
  assets/icon/disk-cleaner-symbolic.svg \
  -o assets/icon/disk-cleaner-symbolic-16.png
```

PNG'ler `assets/icon/` içine düşer; gitignore'da `*.png` yok, commit'lenebilir. Boyutlar:

- **16, 24, 32, 48** — sistem tray / menü
- **64, 128** — desktop genel
- **256, 512** — Flathub, Snap Store thumbnail
- **1024** — yüksek-DPI / macOS uyumluluğu (gerekirse)

## Tasarım notları

- Renk paleti UI'daki treemap palette ile **uyumlu** — `tile-a/b/c/d` gradient stop'ları DESIGN_PRINCIPLES.md'deki dark-mode palette ile aynı aileden.
- Disk gövdesi (`#1d4e83 → #5da9e0`) Codechu marka mavisi.
- 16px'te detay kaybolur — symbolic varyant bu yüzden ayrı.
- Tasarımcı yenilemesi gerekirse: metafor sabit kalsın (disk + treemap + sweep), palette güncellenebilir.
