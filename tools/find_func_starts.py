"""Find ARM function starts in a raw code blob, for seeding Ghidra.

usage: python3 -I find_func_starts.py code.bin base_hex code_end_hex vtables.txt > seeds.txt

Kept as starts:
  - targets of BL instructions,
  - vtable entries (ghidra/bin/vtables.txt: "addr count e1 e2 ..."),
  - `push {..., lr}` only when the previous word ends a function (return, unconditional
    branch) or is not code. A push in 2nd position (e.g. operator_new starts with
    `cmp r0, #0`) must not become a start: it splits the function and makes Ghidra
    believe the first half never returns.
"""
import struct, sys

blob = open(sys.argv[1], 'rb').read()
base, end = int(sys.argv[2], 16), int(sys.argv[3], 16)
W = lambda a: struct.unpack_from('<I', blob, a - base)[0]


def ends_flow(w):
    if w >> 28 != 0xE:
        return False
    if w & 0x0ffffff0 == 0x012fff10:                       # bx rN
        return True
    if (w & 0x0e000000) == 0x0a000000 and not (w >> 24) & 1:  # b (not bl)
        return True
    if (w & 0x0e108000) == 0x08108000:                     # ldm/pop with pc
        return True
    if (w & 0x0c10f000) == 0x0410f000:                     # ldr pc, [...]
        return True
    if (w & 0x0de0f000) == 0x01a0f000:                     # mov pc, rN
        return True
    return False


starts = set()
for a in range(base + 0x20, end, 4):
    w = W(a)
    if w >> 28 == 0xE and (w & 0x0f000000) == 0x0b000000:  # bl
        off = (w & 0xffffff) | (0xff000000 if w & 0x800000 else 0)
        t = (a + 8 + (off << 2)) & 0xffffffff
        if base <= t < end:
            starts.add(t)
    if (w & 0xffff4000) == 0xe92d4000 and ends_flow(W(a - 4)):  # push {.., lr}
        starts.add(a)
for line in open(sys.argv[4]):
    for x in line.split()[2:]:
        t = int(x, 16)
        if base <= t < end:
            starts.add(t)
for t in sorted(starts):
    print(f'{t:#010x}')
