# Screenshots

AppData (`packaging/disk-cleaner.appdata.xml`) raw URL ile bu dosyalara
referans verir. Flathub validator dosyaların erişilebilir + min 624×351
olduğunu doğrular.

## Layout

Dört set var — iki dil × iki tema:

```
assets/screenshots/
├── cli/        ← CLI screenshots (terminal output)
├── en/light/   ← English UI, light theme
├── en/dark/    ← English UI, dark theme
├── tr/light/   ← Türkçe UI, light theme
└── tr/dark/    ← Türkçe UI, dark theme
```

GUI setlerinin her biri 5 dosya: `mainwindow.png`, `suggestion.png`,
`cleanup.png`, `treemap.png`, `sunburst.png` (hepsi 910×676).

CLI seti 6 dosya:

| Dosya | Komut | Ne gösterir |
|-------|-------|-------------|
| `help.png` | `disk-cleaner --help` | Tam usage + epilog'daki yeni örnekler |
| `scan-system.png` | `--scan --sources system --format table` | Renkli risk rozetleriyle tablo |
| `scan-json.png` | `--non-interactive --scan --sources system --format json` | Script-mode JSON çıkışı |
| `watchdog.png` | `--watchdog-status` | Renkli ● rozetli RUNNING + zenginleştirilmiş alanlar (pid, uptime, threshold, interval, last event) |
| `clean-picker.png` | `--scan --clean --dry-run --sources system` (interaktif) | Multiselect picker prompt'u: "Pick items to clean" + kutucuklar + hint |
| `clean-dry-run.png` | `--clean --dry-run --sources system -y` | Picker'ı atlayarak `[TAMAM]` rozetli son özet |

README.md / README.tr.md `<picture>` element ile GitHub'ın
`prefers-color-scheme` sorgusuna göre otomatik geçiş yapar.

## Otomatik yeniden üretim

Tüm görüntüler Disk Cleaner'ın control API'si üzerinden Xvfb sanal
display'inde reproducible şekilde yakalanır.

### Adımlar

```bash
# 1. Fixture HOME
TEST_HOME=/tmp/dc-shots-final
rm -rf $TEST_HOME && mkdir -p $TEST_HOME/.cache/{mozilla,chromium,thumbnails}
mkdir -p $TEST_HOME/Downloads $TEST_HOME/workspace/{project-a,project-b}
mkdir -p $TEST_HOME/.config/codechu/disk-cleaner
mkdir -p $TEST_HOME/.local/share/Trash/files
dd if=/dev/urandom of=$TEST_HOME/Downloads/big-iso.iso bs=1M count=800
dd if=/dev/urandom of=$TEST_HOME/.cache/chromium/cache.bin bs=1M count=240
dd if=/dev/urandom of=$TEST_HOME/.cache/mozilla/cache.bin bs=1M count=180
dd if=/dev/urandom of=$TEST_HOME/.cache/thumbnails/thumbs.bin bs=1M count=60
dd if=/dev/urandom of=$TEST_HOME/.local/share/Trash/files/trash.bin bs=1M count=150
for p in project-a project-b; do
  mkdir -p $TEST_HOME/workspace/$p/{node_modules,build}
  dd if=/dev/urandom of=$TEST_HOME/workspace/$p/node_modules/big.bin bs=1M count=120
  dd if=/dev/urandom of=$TEST_HOME/workspace/$p/build/cache.bin bs=1M count=80
done

# 2. Xvfb (snap env leak için env -i şart)
Xvfb :99 -screen 0 1280x720x24 -ac &
sleep 1

# 3. Capture (script repo'da değil — /tmp/capture_shots.sh playbook):
#    Args: LANG=en|tr  THEME=light|dark  OUT_DIR=assets/screenshots/<lang>/<theme>
#    Her çağrı settings.json yazıp uygulamayı başlatır, 5 görüntüyü API
#    ile yakalar (set_tab, set_entry, click scan), sonra exit eder.
for lang in en tr; do
  for theme in light dark; do
    bash /tmp/capture_shots.sh $lang $theme assets/screenshots/$lang/$theme
  done
done

# 4. Cleanup
pkill -9 -f "Xvfb :99"
```

## CLI screenshots yeniden üretimi

CLI shotları Xvfb :99 üzerinde `xterm` ile yakalanır; `import`
(ImageMagick) xterm pencere ID'sine göre crop yapar.

```bash
# Xvfb başlat (snap env leak için env -i)
env -i HOME=$HOME PATH=$PATH Xvfb :99 -screen 0 1400x1100x24 -ac &
sleep 1

shoot() {  # shoot <out.png> <geom> <wait> <cmd>
  DISPLAY=:99 xterm -title DCSHOT -geometry "$2" \
    -fa "DejaVu Sans Mono" -fs 10 -bg "#1e1e2e" -fg "#cdd6f4" \
    -e bash -c "$4; echo; echo '--- end ---'; sleep 120" &
  PID=$!; sleep "$3"
  WID=$(DISPLAY=:99 xwininfo -root -tree | grep '"DCSHOT"' | head -1 | awk '{print $1}')
  DISPLAY=:99 import -window "$WID" "$1"
  kill $PID 2>/dev/null; wait 2>/dev/null
}

cd /home/onur/workspace/disk-space
DC='python3 -c "from disk_cleaner.cli import main; main()"'

shoot assets/screenshots/cli/help.png         120x90 2 "$DC --help"
shoot assets/screenshots/cli/scan-system.png  110x42 8 "$DC --scan --sources system --format table"
shoot assets/screenshots/cli/scan-json.png    90x36  8 "$DC --non-interactive --scan --sources system --format json 2>/dev/null | head -32"
$DC --watchdog-start && sleep 1
shoot assets/screenshots/cli/watchdog.png     70x14  2 "$DC --watchdog-status"
$DC --watchdog-stop
shoot assets/screenshots/cli/clean-picker.png 110x36 10 "$DC --scan --clean --dry-run --sources system"
shoot assets/screenshots/cli/clean-dry-run.png 110x36 10 "$DC --clean --dry-run --sources system -y"

pkill -9 -f "Xvfb :99"
```

`clean-picker.png` interaktif picker'ı durmuş haliyle yakalar (10s
gecikmeyle multiselect ekrandadır, hiçbir tuşa basılmaz).
`clean-dry-run.png` ise picker'ı tamamen atlayan komutla (`--clean`
ama `--scan` değil) sonuç özetini gösterir.

## Sıklık

- Major UI değişikliğinde yenile (4 setin hepsi)
- Tema/palet güncellemesi → yenile
- Yeni release öncesi spot kontrol
