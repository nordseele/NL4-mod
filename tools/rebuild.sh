#!/bin/sh
# Rebuild every derived firmware file from the official dmg (none of them are in git).
# usage: tools/rebuild.sh   (from the repo root)
set -eu
cd "$(dirname "$0")/.."
DMG="vendor/Update Nord Lead 4 OS v1.32.dmg"
OUT=ghidra/bin
mkdir -p "$OUT"

mp=$(mktemp -d)
hdiutil attach -readonly -nobrowse -mountpoint "$mp" "$DMG" >/dev/null
trap 'hdiutil detach "$mp" >/dev/null; rmdir "$mp"' EXIT
cp "$mp/Update Nord Lead 4 OS v1.32.app/Contents/Resources/os.cab" "$OUT/os.cab"

python3 -I tools/unpack_oscab.py "$OUT/os.cab" "$OUT/unpacked"
# symbols.txt comes last so its names win over the anonymous seeds
cat tools/funcs_seed.txt tools/symbols.txt > "$OUT/funcs_all.txt"
python3 -I tools/mkelf.py "$OUT/nl4_os132_full.elf" c0000000 "$OUT/funcs_all.txt" \
  "$OUT/unpacked/img1_SRAM_80000000.bin@80000000" \
  "$OUT/unpacked/img1_CODE_c0000000.bin@c0000000" \
  "$OUT/unpacked/img1_ARM0_ffff0020.bin@ffff0020"
shasum -a 256 "$OUT/os.cab" "$OUT/unpacked/"*.bin
