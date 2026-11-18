# Wrap raw ARM LE sections into an ELF32 with sections + function symbols,
# so Ghidra picks ARM, the load addresses, and where to start disassembling.
# usage: python3 -I mkelf.py out.elf entry funcs.txt file@addr [file@addr ...]
import struct, sys

out, entry, funcs_path = sys.argv[1], int(sys.argv[2], 16), sys.argv[3]
segs = []
for a in sys.argv[4:]:
    path, addr = a.rsplit('@', 1)
    segs.append((open(path, 'rb').read(), int(addr, 16)))
funcs = sorted({int(l, 16) for l in open(funcs_path) if l.strip()})

EH, PH, SH = 52, 32, 40
n = len(segs)
off = EH + PH * n
phdrs, body, seg_off = b'', b'', []
for data, addr in segs:
    seg_off.append(off + len(body))
    phdrs += struct.pack('<8I', 1, off + len(body), addr, addr, len(data), len(data), 5, 4)  # PT_LOAD R+X
    body += data + b'\0' * (-len(data) % 4)

def sec_of(va):
    for i, (data, addr) in enumerate(segs):
        if addr <= va < addr + len(data):
            return i + 1  # section index (0 is null)

# string + symbol tables: "$a" mapping symbol at each segment start forces ARM mode
strtab, syms = b'\0', [b'\0' * 16]
def sym(name, va, kind, shndx):
    global strtab
    o = len(strtab); strtab += name.encode() + b'\0'
    syms.append(struct.pack('<IIIBBH', o, va, 0, kind, 0, shndx))
for i, (_, addr) in enumerate(segs):
    sym('$a', addr, 0x00, i + 1)  # STB_LOCAL, STT_NOTYPE
nlocal = len(syms)
for va in funcs:
    s = sec_of(va)
    assert s, hex(va)
    sym(f'fn_{va:08x}', va, 0x12, s)  # STB_GLOBAL, STT_FUNC
symtab = b''.join(syms)

names = [''] + [f'.seg_{a:08x}' for _, a in segs] + ['.symtab', '.strtab', '.shstrtab']
shstr, name_off = b'', []
for nm in names:
    name_off.append(len(shstr)); shstr += nm.encode() + b'\0'

tail = off + len(body)
symtab_off = tail; strtab_off = symtab_off + len(symtab); shstr_off = strtab_off + len(strtab)
sh_off = shstr_off + len(shstr); sh_off += -sh_off % 4
shdrs = b'\0' * SH
for i, (data, addr) in enumerate(segs):
    shdrs += struct.pack('<10I', name_off[i + 1], 1, 6, addr, seg_off[i], len(data), 0, 0, 4, 0)  # PROGBITS AX
k = n + 1
shdrs += struct.pack('<10I', name_off[k], 2, 0, 0, symtab_off, len(symtab), k + 1, nlocal, 4, 16)  # SYMTAB
shdrs += struct.pack('<10I', name_off[k + 1], 3, 0, 0, strtab_off, len(strtab), 0, 0, 1, 0)       # STRTAB
shdrs += struct.pack('<10I', name_off[k + 2], 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)         # SHSTRTAB

ident = b'\x7fELF' + bytes([1, 1, 1]) + b'\0' * 9
ehdr = ident + struct.pack('<HHIIIIIHHHHHH', 2, 40, 1, entry, EH, sh_off, 0x05000000, EH, PH, n, SH, len(names), k + 2)
blob = ehdr + phdrs + body + symtab + strtab + shstr
blob += b'\0' * (sh_off - len(blob)) + shdrs
open(out, 'wb').write(blob)

# self-check: segments and symbols read back
b = open(out, 'rb').read()
for i, (data, addr) in enumerate(segs):
    _, o, va, _, sz, _, _, _ = struct.unpack_from('<8I', b, EH + PH * i)
    assert va == addr and b[o:o + sz] == data
assert len(b[symtab_off:symtab_off + len(symtab)]) // 16 == 1 + n + len(funcs)
print('ok', out, [hex(a) for _, a in segs], len(funcs), 'fonctions')
