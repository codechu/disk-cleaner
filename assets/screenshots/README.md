# Screenshots

AppData (`packaging/disk-cleaner.appdata.xml`) raw URL ile bu dosyalara
referans verir. Flathub validator dosyaların erişilebilir + min 624×351
olduğunu doğrular.

## Layout

Dört set var — iki dil × iki tema:

```
assets/screenshots/
├── en/light/   ← English UI, light theme
├── en/dark/    ← English UI, dark theme
├── tr/light/   ← Türkçe UI, light theme
└── tr/dark/    ← Türkçe UI, dark theme
```

Her set 5 dosya: `mainwindow.png`, `suggestion.png`, `cleanup.png`,
`treemap.png`, `sunburst.png` (hepsi 910×676).

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

## Sıklık

- Major UI değişikliğinde yenile (4 setin hepsi)
- Tema/palet güncellemesi → yenile
- Yeni release öncesi spot kontrol
