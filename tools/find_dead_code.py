"""Find CODE ranges of the NL4 OS that nothing can reach, to hold patch code (build.py DEAD).

  python3 -I tools/find_dead_code.py [count]

A range [a, b) of consecutive functions (ghidra/bin/funcs_all.txt) is kept when:
  - no word of any unpacked image (CODE, SRAM, ARM0, image 2) points into it (vtables,
    literal pools, jump tables, function pointers);
  - no B/BL, PC-relative load (LDR/LDRH/LDC [pc, #]) or ADR (ADD/SUB rd, pc, #) from
    outside lands inside it (a shared literal pool would show up here);
  - the word before it is an unconditional return or branch (no fallthrough into it).
Missed on purpose: addresses built at run time from an outside base + offset (the menu
vtables do that, docs/menus.md), so only ranges inside the code area are listed.
"""
import bisect, glob, struct, sys

B = 0xc0000000
TEXT_END = 0xc01bc000      # code area; tables and strings start after (first vtable 0xc01bcc80)
code = open('ghidra/bin/unpacked/img1_CODE_c0000000.bin', 'rb').read()
w = struct.unpack('<%dI' % (len(code) // 4), code[:len(code) // 4 * 4])


def imm(x):
    r, v = (x >> 8) & 15, x & 255
    return ((v >> (2 * r)) | (v << (32 - 2 * r))) & 0xffffffff


refs = []                  # (target, source address or None for a data word)
for p in glob.glob('ghidra/bin/unpacked/img*_*.bin'):
    d = open(p, 'rb').read()
    refs += [(v, None) for v in struct.unpack('<%dI' % (len(d) // 4), d[:len(d) // 4 * 4])
             if B <= v < B + len(code)]
for i, x in enumerate(w):
    a = B + 4 * i
    if x >> 28 == 0xf:
        continue
    up = x & 0x00800000
    if x & 0x0e000000 == 0x0a000000:                                   # B, BL
        off = x & 0xffffff
        refs.append((a + 8 + 4 * (off - (1 << 24) if off & 0x800000 else off), a))
    elif x & 0x0e0f0000 == 0x040f0000:                                 # LDR/STR [pc, #imm12]
        refs.append((a + 8 + ((x & 0xfff) if up else -(x & 0xfff)), a))
    elif x & 0x0e4f0090 == 0x004f0090:                                 # LDRH/LDRD [pc, #imm8]
        o = (x >> 4) & 0xf0 | x & 0xf
        refs.append((a + 8 + (o if up else -o), a))
    elif x & 0x0fef0000 == 0x028f0000:                                 # ADD rd, pc, #
        refs.append((a + 8 + imm(x), a))
    elif x & 0x0fef0000 == 0x024f0000:                                 # SUB rd, pc, #
        refs.append((a + 8 - imm(x), a))
    elif x & 0x0e1f0000 == 0x0c1f0000:                                 # LDC [pc, #]
        refs.append((a + 8 + ((x & 0xff) * 4 if up else -(x & 0xff) * 4), a))
refs.sort(key=lambda r: r[0])
targets = [t for t, _ in refs]
funcs = sorted(int(l.split()[0], 16) for l in open('ghidra/bin/funcs_all.txt') if l.strip())
funcs = [f for f in funcs if B <= f < TEXT_END] + [TEXT_END]


def outside_ref(a, b):
    i = bisect.bisect_left(targets, a)
    while i < len(targets) and targets[i] < b:
        s = refs[i][1]
        if s is None or not a <= s < b:
            return True
        i += 1
    return False


def ends_flow(a):
    x = w[(a - B) // 4 - 1]
    return x >> 28 == 0xe and (x & 0x0f000000 == 0x0a000000            # B
                               or x & 0x0ffffff0 == 0x012fff10         # BX rn
                               or x & 0x0e108000 == 0x08108000         # LDM {.., pc}
                               or x & 0x0ff0f000 == 0x0490f000         # LDR pc, [sp], #
                               or x == 0xe1a0f00e)                     # MOV pc, lr


def dead_ranges():
    runs, i = [], 0
    while i < len(funcs) - 1:
        a = funcs[i]
        if not ends_flow(a) or outside_ref(a, funcs[i + 1]):
            i += 1
            continue
        j = i + 1
        while j < len(funcs) - 1 and not outside_ref(a, funcs[j + 1]):
            j += 1
        runs.append((a, funcs[j]))
        i = j
    return runs


if __name__ == '__main__':
    runs = sorted(dead_ranges(), key=lambda r: r[0] - r[1])
    for a, b in runs[:int(sys.argv[1]) if len(sys.argv) > 1 else 20]:
        print(f'{a:#x} {b:#x} {b - a:#x}')
    print(f'total {sum(b - a for a, b in runs):#x} in {len(runs)} ranges')
