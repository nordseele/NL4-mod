#!/bin/sh
# Copy Nord's updater app out of the official dmg and put our os.cab inside it.
#   tools/patch/make_updater.sh build/palier2_os.cab      -> build/palier2_os.app
# The app reads Contents/Resources/os.cab (CImageTransferFrame::ReadOSResource). Replacing
# it breaks the bundle signature, so the copy is re-signed ad hoc and un-quarantined.
set -eu
cd "$(dirname "$0")/../.."
CAB=$1
APP="${CAB%.cab}.app"
DMG="vendor/Update Nord Lead 4 OS v1.32.dmg"
mp=$(mktemp -d)
hdiutil attach -readonly -nobrowse -mountpoint "$mp" "$DMG" >/dev/null
trap 'hdiutil detach "$mp" >/dev/null; rmdir "$mp"' EXIT
rm -rf "$APP"
ditto "$mp/Update Nord Lead 4 OS v1.32.app" "$APP"
cp "$CAB" "$APP/Contents/Resources/os.cab"
xattr -cr "$APP"
codesign --force --deep --sign - "$APP" 2>/dev/null
codesign --verify --deep "$APP"
shasum -a 256 "$APP/Contents/Resources/os.cab"
echo "$APP prêt"
