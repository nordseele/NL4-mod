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
HEAP = 0xc0931538           # end of the firmware's zero fill = first heap address
SBRK_START = 0xc014afd0     # literal pool word of _sbrk (c014af98) holding HEAP
STARTUP = 0xc0404fb4        # startup copy/zero table: [?, src, dst, copy size, zero size]

# Firmware functions our C code calls (names as declared in the .c files).
SYMBOLS = {
    'zone_setup_orig': 0xc00df898,
    'zone_add_follow': 0xc0112b2c,
    'target_note_on_orig': 0xc011129c,
    'slot_queue_note_on_orig': 0xc0028780,
    'build_voices_orig': 0xc00268d0,
    'note_event_orig': 0xc00263b4,
    'midi_bend_in_orig': 0xc0120398,
    'notemap_has': 0xc0016504,
    'notemap_get': 0xc0016464,
    'midi_cc_in_orig': 0xc011ffc4,
    'synth_tick_orig': 0xc0010c34,
    'voice_apply_velocity': 0xc0032098,
    'morph_get': 0xc0118c24,
    'midi_pressure_in_orig': 0xc01202ac,
    'amp_gain_write': 0xc0061a08,
    'voice_morph_eval': 0xc0033538,
    'voice_param_handler': 0xc0029678,
}

PALIER2 = {
    'sources': ['palier2.c'],
    'data': [(0xc040aad8, 4, 36)],                            # zones per note target
    'calls': [(0xc00e0540, 0xc00df898, 'mpe_zone_setup')],     # (site, original target, ours)
}

PALIER3 = {
    'sources': ['palier2.c', 'palier3.c'],
    'data': PALIER2['data'],
    'calls': PALIER2['calls'],
    # (address, original word, our symbol): pointers in data (vtables, literal pools)
    'ptrs': [(0xc011ffac, 0xc011129c, 'mpe_target_note_on'),      # midi_noteon_dispatch
             (0xc01bde58, 0xc00268d0, 'mpe_build_voices'),        # note manager vt[2]
             (0xc01bde5c, 0xc00263b4, 'mpe_note_event'),          # note manager vt[3]
             (0xc03bf32c, 0xc0120398, 'mpe_bend_in'),             # three MIDI rx vtables
             (0xc03ed740, 0xc0120398, 'mpe_bend_in'),
             (0xc03edc2c, 0xc0120398, 'mpe_bend_in')],
    # (address, original word, our symbol): instruction replaced by `b ours`
    'branches': [(0xc00119f8, 0xea005b60, 'mpe_queue_note_on'),   # tail call in slot_sink_note_on
                 (0xc001ccf4, 0xe5913000, 'mpe_voice_pitch_offset')],  # replaces the function
}

PALIERS = {
    'palier2': PALIER2,
    'palier3': PALIER3,
    'palier4': {
        'sources': PALIER3['sources'] + ['palier4.c'],
        'data': PALIER3['data'],
        'calls': PALIER3['calls'],
        'ptrs': PALIER3['ptrs'] + [
            (0xc03bf334, 0xc011ffc4, 'mpe_cc_in'),                    # three MIDI rx vtables
            (0xc03ed748, 0xc011ffc4, 'mpe_cc_in'),
            (0xc03edc34, 0xc011ffc4, 'mpe_cc_in'),
            (0xc0000480, 0xc0010c34, 'mpe_synth_tick')],              # level-4 handler (init)
        'branches': PALIER3['branches'],
    },
    'palier5': {                                                       # replaces palier4.c
        'sources': PALIER3['sources'] + ['palier5.c'],
        'data': PALIER3['data'],
        'calls': PALIER3['calls'],
        'ptrs': [e for e in PALIER3['ptrs'] if e[0] not in (0xc01bde58, 0xc01bde5c)] + [
            (0xc01bde58, 0xc00268d0, 'mpe5_build_voices'),            # palier 3 + refresh
            (0xc01bde5c, 0xc00263b4, 'mpe5_note_event'),
            (0xc0000480, 0xc0010c34, 'mpe_synth_tick')],
        # CC reach midi_cc_in through a this-adjusting thunk (sub r0, #24; b midi_cc_in), not
        # through the vtable entry palier 4 replaced: palier 4 never saw a CC74.
        'branches': PALIER3['branches'] + [(0xc01202a8, 0xeaffff45, 'mpe_cc_in')],
    },
}
PALIERS['palier6'] = dict(PALIERS['palier5'],                         # replaces palier5.c: + Z, smoothing
    sources=PALIER3['sources'] + ['palier6.c'],
    branches=PALIERS['palier5']['branches']
             + [(0xc0120394, 0xeaffffc4, 'mpe_pressure_in')],            # pressure thunk
    heap_bss=True)
PALIERS['palier7'] = dict(PALIERS['palier6'],                         # Y per parameter, like the wheel
    sources=PALIER3['sources'] + ['palier7.c'])
PALIERS['palier8'] = dict(PALIERS['palier7'],                         # playable Z -> Level
    sources=PALIER3['sources'] + ['palier8.c'])
PALIERS['palier5diag'] = dict(PALIERS['palier5'],                     # palier 5 + audible diagnostic
    sources=PALIER3['sources'] + ['palier5diag.c'],
    branches=[(0xc00119f8, 0xea005b60, 'mpe_queue_note_on'),
              (0xc001ccf4, 0xe5913000, 'mpe5_voice_pitch_offset'),
              (0xc01202a8, 0xeaffff45, 'mpe_cc_in')])


def bl(site, target, op=0xeb000000):
    off = (target - site - 8) >> 2
    assert -(1 << 23) <= off < (1 << 23), 'BL out of range'
    return op | (off & 0xffffff)


def word(code, addr):
    return struct.unpack_from('<I', code, addr - BASE)[0]


def put(code, addr, old, new):
    assert word(code, addr) == old, f'{addr:#x}: {word(code, addr):#x} != attendu {old:#x}'
    struct.pack_into('<I', code, addr - BASE, new)


def compile_and_link(srcs, out, heap_bss=False):
    # heap_bss: zeroed variables go to the start of the heap (HEAP), which main() moves up,
    # instead of filling the code gap.
    ld = os.path.join(out, 'patch.ld')
    bss = '*(.bss*) *(COMMON)'
    with open(ld, 'w') as f:
        f.write(f'MEMORY {{ gap (rx) : ORIGIN = {CODE_END:#x}, LENGTH = {GAP_END - CODE_END:#x}\n'
                f'         ram (rw) : ORIGIN = {HEAP:#x}, LENGTH = 0x1000 }}\n'
                'SECTIONS {\n  .text : { *(.text.entry) *(.text*) *(.rodata*) *(.data*) '
                + ('} > gap\n  .hbss (NOLOAD) : { ' + bss + ' . = ALIGN(8); mpe_bss_end = .; } > ram\n'
                   if heap_bss else bss + ' } > gap\n')
                + '  /DISCARD/ : { *(.comment) *(.ARM.attributes) }\n}\n')
        for name, addr in SYMBOLS.items():
            f.write(f'{name} = {addr:#x};\n')
    elf, binf = (os.path.join(out, 'patch' + e) for e in ('.elf', '.bin'))
    cflags = ['-Os', '-marm', '-march=armv5te', '-mfloat-abi=soft', '-ffreestanding', '-fno-builtin',
              '-nostdlib', '-fno-common', '-fno-pic', '-ffunction-sections', '-Wall', '-Wextra', '-Werror']
    objs = []
    for src in srcs:
        objs.append(os.path.join(out, os.path.basename(src)[:-2] + '.o'))
        subprocess.run(['arm-none-eabi-gcc', *cflags, '-c', src, '-o', objs[-1]], check=True)
    subprocess.run(['arm-none-eabi-ld', '-T', ld, *objs, '-o', elf], check=True)
    sects = subprocess.run(['arm-none-eabi-objdump', '-h', elf], check=True, capture_output=True, text=True).stdout
    assert '.data' not in sects and '.bss' not in sects, 'variables hors des sections prévues'
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
    heap_bss = spec.get('heap_bss', False)
    blob, syms = compile_and_link([os.path.join(HERE, f) for f in spec['sources']], out, heap_bss)
    blob += b'\0' * (-len(blob) % 8)                    # zero fill uses 8-byte stores
    assert CODE_END + len(blob) <= GAP_END, f'patch trop gros : {len(blob):#x} octets'
    code = bytearray(open(os.path.join(ROOT, 'ghidra', 'bin', 'unpacked', 'img1_CODE_c0000000.bin'), 'rb').read())
    assert len(code) == CODE_END - BASE, 'CODE inattendu'
    new_end = CODE_END + len(blob)
    put(code, STARTUP + 12, CODE_END - BASE, new_end - BASE)       # copy size (src == dst: no copy)
    zero_end = CODE_END + word(code, STARTUP + 16)
    assert zero_end == HEAP
    if heap_bss:                                         # zero fill and heap start move past our variables
        zero_end = syms['mpe_bss_end']
        put(code, SBRK_START, HEAP, zero_end)
    put(code, STARTUP + 16, HEAP - CODE_END, zero_end - new_end)  # zero fill starts after us
    for addr, old, new in spec['data']:
        put(code, addr, old, new)
    for site, orig, ours in spec['calls']:
        put(code, site, bl(site, orig), bl(site, syms[ours]))
    for addr, old, ours in spec.get('ptrs', []):
        put(code, addr, old, syms[ours])
    for site, old, ours in spec.get('branches', []):
        put(code, site, old, bl(site, syms[ours], 0xea000000))
    code += blob
    path = os.path.join(out, 'img1_CODE_c0000000.bin')
    open(path, 'wb').write(code)
    cab = os.path.join(ROOT, 'build', f'{name}_os.cab')
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools', 'pack_oscab.py'),
                    os.path.join(ROOT, 'ghidra', 'bin', 'os.cab'), cab, f'CODE={path}'], check=True)
    ours = {e[2] for k in ('calls', 'ptrs', 'branches') for e in spec.get(k, [])}
    print(f'{name}: {len(blob):#x} octets en {CODE_END:#x} ; '
          + ', '.join(f'{k}={syms[k]:#x}' for k in sorted(ours)))


if __name__ == '__main__':
    main(sys.argv[1])
