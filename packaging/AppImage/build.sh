#!/usr/bin/env bash
# Codechu Disk Cleaner — AppImage build script
# linuxdeploy + gtk + python plugin. ubuntu-22.04 üstünde test edildi.
set -euo pipefail

ARCH=${ARCH:-x86_64}
APP=CodechuDiskCleaner
APPDIR=$APP.AppDir
VERSION=${VERSION:-$(grep -E '^version' pyproject.toml | head -1 | cut -d'"' -f2)}

cd "$(dirname "$0")/../.."   # repo root

rm -rf "$APPDIR" CodechuDiskCleaner-*.AppImage

# Skeleton
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/lib/python3" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
         "$APPDIR/usr/share/metainfo"

# Python paketi (--target ile bundle)
python3 -m pip install --target "$APPDIR/usr/lib/python3" --no-deps .

# Desktop / AppStream / Icon
cp packaging/disk-cleaner.desktop          "$APPDIR/usr/share/applications/"
cp packaging/disk-cleaner.appdata.xml      "$APPDIR/usr/share/metainfo/com.codechu.DiskCleaner.metainfo.xml"
cp packaging/icon.svg                      "$APPDIR/usr/share/icons/hicolor/scalable/apps/disk-cleaner.svg"
# linuxdeploy top-level icon arar
cp packaging/icon.svg                      "$APPDIR/disk-cleaner.svg"
cp packaging/disk-cleaner.desktop          "$APPDIR/disk-cleaner.desktop"

# AppRun — Python + GTK env
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PYTHONPATH="$HERE/usr/lib/python3:${PYTHONPATH:-}"
export GI_TYPELIB_PATH="$HERE/usr/lib/x86_64-linux-gnu/girepository-1.0:${GI_TYPELIB_PATH:-}"
export LD_LIBRARY_PATH="$HERE/usr/lib/x86_64-linux-gnu:$HERE/usr/lib:${LD_LIBRARY_PATH:-}"
export XDG_DATA_DIRS="$HERE/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
exec python3 -m disk_cleaner "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Build via linuxdeploy + GTK plugin
DEPLOY_GTK_VERSION=3 linuxdeploy-${ARCH}.AppImage \
    --appdir="$APPDIR" \
    --plugin=gtk \
    --plugin=python \
    --output=appimage

# Rename to versioned filename
mv "${APP}-${ARCH}.AppImage" "${APP}-${VERSION}-${ARCH}.AppImage" 2>/dev/null || true

ls -lah CodechuDiskCleaner-*.AppImage
