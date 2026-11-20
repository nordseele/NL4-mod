# `os.cab` format (Nord Lead 4 OS v1.32)

Source: `Update Nord Lead 4 OS v1.32.app/Contents/Resources/os.cab` (3,074,576 bytes,
SHA-256 `42bbad95…ed16819`). The Mac program (`Nord OS Update`, wxWidgets) decompresses
nothing: it splits the file into sections and sends them over USB
(`CITProtocol::ParseAndSendBinFileSections`). Decompression happens on the keyboard.
Update protocol: `docs/update-protocol.md`.

## File header (big-endian)  [sure: read in the updater, `Zevs::CCabHeader`]

Four (offset, size) pairs, one per program; empty pairs are 0. The updater checks that
they do not overlap.

| Offset | Value | Meaning |
|---|---|---|
| 0x00 / 0x04 | 0x20 / 0x2a2b9e | image 1 (OS): offset, size |
| 0x08 / 0x0c | 0x2a2bbe / 0x4be52 | image 2 (factory test): offset, size |
| 0x10–0x1c | 0 | unused |

## Image header (0x2d4 bytes, big-endian)  [sure: `Zevs::CBinHeader`]

| Offset | Type | Meaning |
|---|---|---|
| 0x00 | u16 | version (0x84 = 1.32; 0x70 for image 2) |
| 0x02 | u8 | type (must be 1) |
| 0x03 | u8 | 0 |
| 0x04 | u16 | build (0x32a = 810) |
| 0x06 | u16 | **header sum** = `~(sum of the bytes of [0x08, 0x2d4)) & 0xffff` |
| 0x08 | u32 | start address (0x00640000; must not be 0xffffffff) |
| 0x0c | u32 | 0 |
| 0x10 | u32 | number of sections (3) |
| 0x14 | 16 × 0x2c | section slots (3 used) |

Section offsets count from the start of the image (this header). Sections follow each
other without alignment, right after the header (0x2d4).

### What the Mac updater checks before sending  [sure]
`CUpdateEngine::ParseAndDisplayFileInfo`: `CCabFile::Verify` (consistent pairs), then
`CBinFile::Verify` on image 1: non-empty header, header sum, type 1, start address ≠ −1,
and for each section: tag in printable ASCII and 16-bit sum of the sent bytes (`~Get16` =
low 16 bits of our checksum, compressed if the section is). Failure → "OS BinFile seems
broken". Version and build are then shown (`GetOSString`).

## Sections

| Image | Tag | Address | Size | Storage |
|---|---|---|---|---|
| 1 (OS) | SRAM | 0x80000000 | 0x1c24 | raw |
| 1 (OS) | CODE | 0xc0000000 | 0x40b530 | LZO1X, 0x2a0a3e bytes |
| 1 (OS) | ARM0 | 0xffff0020 | 0x268 | raw |
| 2 (factory test) | SRAM | 0x80000000 | 0x1490 | raw |
| 2 (factory test) | CODE | 0xc0000000 | 0x89098 | LZO1X, 0x4a472 bytes |
| 2 (factory test) | ARM0 | 0xffff0020 | 0x27c | raw |

The addresses match the memory map of the TI **AM1705** seen on the board (OMAP-L137
family, ARM926 only, `docs/hardware.md`): shared RAM 0x80000000, SDRAM (EMIFB)
0xc0000000, ARM local RAM and high vectors 0xffff0000. Little-endian ARM. The entry point
(0xffff0040) does `ldr pc, =0xc0000000`.

## Section offsets  [corrected on 2026-11-18]

A section occupies `size` bytes (or `compressed size`) from
`start of the image + 0x20 + offset`. Its bytes are loaded as they are at the load
address.

Previous mistake: the offset was counted from the start of the preamble, hence 0x20
bytes too early. The 0x20 bytes of "unloaded header" that seemed to appear at the start of
each section were actually **the end of the previous section**: zeros after SRAM, and for
ARM0 the last bytes of the CODE LZO stream, with its end marker `11 00 00`. Each section
was therefore missing its last 0x20 bytes. Addresses already published do not change: the
old CODE image is exactly the start of the new one, which has 0x20 more bytes.

## Compression: LZO1X

Standard LZO1X stream, **with** its end marker. It occupies exactly the compressed size
and gives exactly the declared size (images 1 and 2). The "extra byte" and the liblzo2
"input overrun" noted before came from the shifted offset.

## Checksums: solved  [sure]

For the 6 sections of both images, `tools/unpack_oscab.py` checks them at each
extraction:
- **checksum** = `~(sum of the section's bytes) & 0xffffffff`, unsigned bytes,
  decompressed section;
- **compressed stream checksum** = the same formula on the compressed bytes;
- raw-stored sections: stream checksum = 0.

For a modified firmware: recompute these two sums, the sizes, the offsets, and the image
header sum. `tools/pack_oscab.py` does it (see below). The Mac program also has a CRC-32
(`Zevs::CRC::CCRC32`: reflected CRC-32, initial register 0xFFFFFFFF, final complement;
`CCRC32X` returns 0 for a null register). It is used for transport ("Message CRC error"),
not for sections.

## Reference hashes (payloads, output of `tools/rebuild.sh`)

```
img1_ARM0_ffff0020.bin  7554211a164a4b2aa7e9a2ee7adfbb002c621de1885ddddba9ef0935476e6cc9
img1_CODE_c0000000.bin  c29d959d9c0e9ea09c9bea733321948de9fba412b982d067081c5c19e609cc6d
img1_SRAM_80000000.bin  ada475d4618926caa6eff8905fb18ad71ef1072062214c2ad44ef18bb5c2a89a
img2_ARM0_ffff0020.bin  0c34341743c9644ce78349adb4967491d7ee399c43354f8246d2e757d59e74e8
img2_CODE_c0000000.bin  376e1b11ed8ae04bdd288787aa803ce0b7c8887a5da0c32e1a8ee5751e4dbbef
img2_SRAM_80000000.bin  d9ebae40678cb0dfe92ad578fdf520446263a422e59d7569f79c61b705947f8c
```

## Rebuilding `os.cab`: `tools/pack_oscab.py`  [checked off the instrument]

Replaces sections of image 1 (`TAG=file`), recompresses, recomputes sums, sizes, offsets
and header sum, copies image 2, then reads the result back the way the updater and the
keyboard do (full decompression and check of all sums).

- **Round trip without changes**: the six re-extracted sections are identical byte for
  byte to the originals.
- **Compression**: Nord uses neither LZO1X-1 nor LZO1X-999 as is (CODE stream of
  2,755,134 bytes). With python-lzo level 9 (LZO1X-999): 2,555,912 bytes, complete file of
  2,875,354 bytes (**200 KB less than the official one**). Without python-lzo, fallback to
  a Python LZO1X-1: 2,978,357 bytes (+223 KB).
- The produced streams are decompressed identically by the real liblzo2 (python3-lzo,
  throwaway container) and by our decoder.
- The keyboard's Update program accepts the file: checked in stage 1 (`docs/patches.md`).
