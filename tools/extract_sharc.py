#!/usr/bin/env python3
"""Extract the two SHARC (ADSP-21489) boot streams embedded in the NL4 OS CODE section.

Each stream is stored as [ADI 214xx 32-bit boot stream][u32 word count]: a 256-instruction
boot kernel, then blocks (ZERO_LDATA / INIT_L16 / INIT_L32 ...) ending with FINAL_INIT.
The ARM sends them at boot (loader fn_c010cc98, pointers at 0xc010cddc / 0xc010cde0).

usage: python3 -I tools/extract_sharc.py ghidra/bin/unpacked/img1_CODE_c0000000.bin OUTDIR
"""
import os, struct, sys

BASE = 0xc0000000
STREAMS = (0xc03c5720, 0xc03d9334)
KERNEL = 256 * 6
SIZES = {3: lambda c: (c + 1) // 2 * 4, 4: lambda c: c * 4, 5: lambda c: (c + 1) // 2 * 12,
         6: lambda c: c * 8}


def walk(b, start):
    off, blocks = start + KERNEL, 0
    while True:
        tag, count, addr = struct.unpack_from('<III', b, off)
        size = KERNEL if tag == 0 else SIZES[tag](count) if tag in SIZES else 0
        assert tag <= 10, f'bad block tag {tag:#x} at {BASE + off:#x}'
        off += 12 + size
        blocks += 1
        if tag == 0:  # FINAL_INIT
            return off, blocks


def main():
    code, out = sys.argv[1], sys.argv[2]
    b = open(code, 'rb').read()
    os.makedirs(out, exist_ok=True)
    for n, a in enumerate(STREAMS, 1):
        s = a - BASE
        end, blocks = walk(b, s)
        words = struct.unpack_from('<I', b, end)[0]
        assert end - s == words * 4, f'stream {n}: length {end - s:#x} != trailer {words * 4:#x}'
        path = os.path.join(out, f'sharc{n}_{a:08x}.ldr')
        open(path, 'wb').write(b[s:end])
        print(f'{path}: {end - s:#x} bytes, {blocks} blocks, OK')


if __name__ == '__main__':
    main()
