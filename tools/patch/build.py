"""Build a patched NL4 OS (os.cab) from one palier's C file. Runs in the nl4-arm container:

  docker build -t nl4-arm tools/patch
  docker run --rm -v "$PWD":/w nl4-arm python3 -I tools/patch/build.py palier2

Our code is linked into the 0xad0-byte gap between the end of the CODE image (0xc040b530)
and the first static variable (0xc040c000). The startup table (0xc0404fb4) zero-fills from
the end of CODE, so its copy/zero sizes are moved past our code. Every patched word is
checked against its expected original value first. Output: build/<palier>_os.cab.
"""
import os, struct, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, 'tools', 'patch')
BASE = 0xc0000000
CODE_END = 0xc040b530       # end of the official CODE image
GAP_END = 0xc040c000        # first address used by static data
STARTUP = 0xc0404fb4        # startup copy/zero table: [?, src, dst, copy size, zero size]

# Firmware functions our C code calls (names as declared in the .c files).
SYMBOLS = {
    'zone_setup_orig': 0xc00df898,
    'zone_add_follow': 0xc0112b2c,
}

PALIERS = {
    'palier2': {
        'source': 'palier2.c',
        'data': [(0xc040aad8, 4, 36)],                       # zones per note target
        'calls': [(0xc00e0540, 0xc00df898, 'mpe_zone_setup')],  # (site, original target, ours)
    },
}


def bl(site, target):
    off = (target - site - 8) >> 2
    assert -(1 << 23) <= off < (1 << 23), 'BL out of range'
    return 0xeb000000 | (off & 0xffffff)


def word(code, addr):
    return struct.unpack_from('<I', code, addr - BASE)[0]


def put(code, addr, old, new):
    assert word(code, addr) == old, f'{addr:#x}: {word(code, addr):#x} != attendu {old:#x}'
    struct.pack_into('<I', code, addr - BASE, new)


def compile_and_link(src, out):
    ld = os.path.join(out, 'patch.ld')
    with open(ld, 'w') as f:
        f.write(f'MEMORY {{ gap (rx) : ORIGIN = {CODE_END:#x}, LENGTH = {GAP_END - CODE_END:#x} }}\n'
                'SECTIONS {\n  .text : { *(.text.entry) *(.text*) *(.rodata*) } > gap\n'
                '  /DISCARD/ : { *(.comment) *(.ARM.attributes) }\n}\n')
        for name, addr in SYMBOLS.items():
            f.write(f'{name} = {addr:#x};\n')
    obj, elf, binf = (os.path.join(out, 'patch' + e) for e in ('.o', '.elf', '.bin'))
    cflags = ['-Os', '-marm', '-march=armv5te', '-mfloat-abi=soft', '-ffreestanding', '-fno-builtin',
              '-nostdlib', '-fno-common', '-fno-pic', '-ffunction-sections', '-Wall', '-Wextra', '-Werror']
    subprocess.run(['arm-none-eabi-gcc', *cflags, '-c', src, '-o', obj], check=True)
    subprocess.run(['arm-none-eabi-ld', '-T', ld, obj, '-o', elf], check=True)
    sects = subprocess.run(['arm-none-eabi-objdump', '-h', elf], check=True, capture_output=True, text=True).stdout
    assert '.data' not in sects and '.bss' not in sects, 'pas de variables globales dans le patch'
    subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', '-j', '.text', elf, binf], check=True)
    syms = {}
    for line in subprocess.run(['arm-none-eabi-nm', elf], check=True, capture_output=True, text=True).stdout.split('\n'):
        p = line.split()
        if len(p) == 3:
            syms[p[2]] = int(p[0], 16)
    with open(os.path.join(out, 'patch.lst'), 'w') as f:
        f.write(subprocess.run(['arm-none-eabi-objdump', '-d', elf], check=True, capture_output=True, text=True).stdout)
    return open(binf, 'rb').read(), syms


def main(name):
    spec = PALIERS[name]
    out = os.path.join(ROOT, 'build', name)
    os.makedirs(out, exist_ok=True)
    blob, syms = compile_and_link(os.path.join(HERE, spec['source']), out)
    blob += b'\0' * (-len(blob) % 8)                    # zero fill uses 8-byte stores
    assert CODE_END + len(blob) <= GAP_END, f'patch trop gros : {len(blob):#x} octets'
    code = bytearray(open(os.path.join(ROOT, 'ghidra', 'bin', 'unpacked', 'img1_CODE_c0000000.bin'), 'rb').read())
    assert len(code) == CODE_END - BASE, 'CODE inattendu'
    new_end = CODE_END + len(blob)
    put(code, STARTUP + 12, CODE_END - BASE, new_end - BASE)       # copy size (src == dst: no copy)
    zero_end = CODE_END + word(code, STARTUP + 16)
    put(code, STARTUP + 16, zero_end - CODE_END, zero_end - new_end)  # zero fill starts after us
    for addr, old, new in spec['data']:
        put(code, addr, old, new)
    for site, orig, ours in spec['calls']:
        put(code, site, bl(site, orig), bl(site, syms[ours]))
    code += blob
    path = os.path.join(out, 'img1_CODE_c0000000.bin')
    open(path, 'wb').write(code)
    cab = os.path.join(ROOT, 'build', f'{name}_os.cab')
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools', 'pack_oscab.py'),
                    os.path.join(ROOT, 'ghidra', 'bin', 'os.cab'), cab, f'CODE={path}'], check=True)
    print(f'{name}: {len(blob):#x} octets de code en {CODE_END:#x}, '
          f'symboles {", ".join(f"{k}={v:#x}" for k, v in syms.items() if k in [c[2] for c in spec["calls"]])}')


if __name__ == '__main__':
    main(sys.argv[1])
