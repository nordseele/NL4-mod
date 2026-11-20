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
    'target_note_off_orig': 0xc0111424,
    'global_get': 0xc00e270c,
    'global_step': 0xc00e2824,
    'operator_new': 0xc0181b24,
    'param_table_ctor_orig': 0xc010e4f0,
    'app_on_global_orig': 0xc00e0a1c,
    'app_routing_update': 0xc00e04cc,
    'menu_page_add': 0xc0124cec,
    'menu_list_show_page_orig': 0xc0124e7c,
    'pb_entry_ctor': 0xc01001f8,
    'menu_entry_is_active': 0xc0125514,
    'event_done': 0xc0130218,
}

# CODE ranges nothing references (tools/find_dead_code.py): extra room once the gap is full.
DEAD = [(0xc002d1f8, 0xc002daa4), (0xc0021388, 0xc0021a5c)]

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
PALIERS['palier9'] = dict(PALIERS['palier8'],                         # same pitch on two channels
    sources=['palier2.c', 'palier3alias.c', 'palier9.c'],
    ptrs=[e for e in PALIERS['palier8']['ptrs'] if e[0] != 0xc011ffac] + [
        (0xc011ffac, 0xc011129c, 'mpe9_target_note_on'),               # midi_noteon_dispatch
        (0xc011feb0, 0xc0111424, 'mpe9_target_note_off')])             # midi_noteoff_dispatch
PALIERS['palier10'] = dict(PALIERS['palier9'],                       # MPE options in the MIDI menu
    sources=['palier10.c'],                                            # includes palier2/3alias/9
    # global setting 0x21 (saved on 31 bits, max 0 in 1.32) carries our options: max -> 0x1f
    data=PALIERS['palier9']['data'] + [(0xc03c02a4, 0, 0x1f)],
    calls=PALIER2['calls'] + [(0xc00fc0e8, 0xc0124e7c, 'mpe10_menus_done')],   # end of menus_build
    ptrs=PALIERS['palier9']['ptrs'] + [
        (0xc03bf200, 0xc00e0a1c, 'mpe10_on_global')],                  # app: global setting changed
    dead=DEAD,
    # words palier10.c relies on, checked against the original image
    checks=[(0xc03c37b0, [0, 0, 0xc000145c, 0xc00fef50, 0xc0100b80, 0xc00fef48, 0xc00fef4c,
                          0xc0100a20, 0xc00fde6c, 0xc00fde78, 0xc01252ec, 0xc0125354, 0xc0125320,
                          0xc01252e4, 0xc00ffd28, 0xc0100870]),               # PB Mode vtable
            (0xc03c37f0, [0xfffffff4, 0, 0xc00fde84, 0xc0100a94]),       # its +0xc sub-object
            (0xc0100a94, [0xe240000c]),                                # its thunk: sub r0, #12
            (0xc03c029c, [0x21, 0, 0, 0x1f, 0, 0x100, 0xffffffff])])   # descriptor of 0x21
PALIERS['palier10diag'] = dict(PALIERS['palier10'], sources=['palier10diag.c'])  # state on the menu
# Diagnostic: palier 9 with its two note wrappers moved into the dead range palier 10 uses.
# Boots and plays like palier 9 if that range really is dead.
PALIERS['palier9dead'] = dict(PALIERS['palier9'], dead=DEAD,
    force_dead=['mpe9_target_note_on', 'mpe9_target_note_off'])
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


def pack(objs, dead, force=()):
    """Place each code / constant section: the gap first, in source order, then the dead
    ranges, largest first (first fit). Returns linker-script patterns per region."""
    secs, data = [], 0
    for o in objs:
        lines = subprocess.run(['arm-none-eabi-objdump', '-h', o], check=True, capture_output=True,
                               text=True).stdout.split('\n')
        for l in lines:
            p = l.split()
            if len(p) == 7 and p[0].isdigit() and p[6].startswith('2**'):
                name, size, align = p[1], int(p[2], 16), 1 << int(p[6][3:])
                if not size:
                    continue
                if name.startswith(('.text', '.rodata')):
                    secs.append((f'*{os.path.basename(o)}({name})', size, align))
                elif name.startswith('.data'):
                    data += size + 8                                  # + alignment slack
    up = lambda x, a: (x + a - 1) & -a
    room, gap_in, rest = GAP_END - CODE_END - data - 8, [], []
    used = 0                                              # force: sections sent to the dead ranges
    for pat, size, align in secs:                         # first fit: smaller ones still fill the gap
        if any(f'.{f})' in pat for f in force) or up(used, align) + size > room:
            rest.append((pat, size, align))
        else:
            used = up(used, align) + size
            gap_in.append(pat)
    free = [b - a for a, b in dead]
    dead_in = [[] for _ in dead]
    for pat, size, align in sorted(rest, key=lambda s: -s[1]):
        for i in range(len(dead)):
            n = up(dead[i][1] - dead[i][0] - free[i], align) + size
            if n <= dead[i][1] - dead[i][0]:
                free[i] = dead[i][1] - dead[i][0] - n
                dead_in[i].append(pat)
                break
        else:
            raise SystemExit(f'plus de place pour {pat} ({size:#x} octets)')
    return gap_in, dead_in


def compile_and_link(srcs, out, heap_bss=False, dead=(), force=()):
    # heap_bss: zeroed variables go to the start of the heap (HEAP), which main() moves up,
    # instead of filling the code gap.
    # dead: code and constants that do not fit the gap go to these CODE ranges, one output
    # section each (.dead0, .dead1…), placed by pack() below; variables stay in the gap or
    # the heap (the dead ranges may be read-only for all we know).
    ld = os.path.join(out, 'patch.ld')
    bss = '*(.bss*) *(COMMON)'
    elf, binf = (os.path.join(out, 'patch' + e) for e in ('.elf', '.bin'))
    cflags = ['-Os', '-marm', '-march=armv5te', '-mfloat-abi=soft', '-ffreestanding', '-fno-builtin',
              '-nostdlib', '-fno-common', '-fno-pic', '-ffunction-sections', '-Wall', '-Wextra', '-Werror']
    if dead:
        cflags.append('-fdata-sections')
    objs = []
    for src in srcs:
        objs.append(os.path.join(out, os.path.basename(src)[:-2] + '.o'))
        subprocess.run(['arm-none-eabi-gcc', *cflags, '-c', src, '-o', objs[-1]], check=True)
    if dead:
        gap_in, dead_in = pack(objs, dead, force)
        gap_text = (' '.join(gap_in) + ' *(.text) *(.glue_7) *(.glue_7t) *(.vfp11_veneer) *(.v4_bx)'
                    ' *(.data*) ')                               # + linker stubs (empty in ARM mode)
    else:
        gap_text = '*(.text.entry) *(.text*) *(.rodata*) *(.data*) '
    with open(ld, 'w') as f:
        f.write(f'MEMORY {{ gap (rx) : ORIGIN = {CODE_END:#x}, LENGTH = {GAP_END - CODE_END:#x}\n'
                + ''.join(f'         dead{i} (rx) : ORIGIN = {a:#x}, LENGTH = {b - a:#x}\n'
                          for i, (a, b) in enumerate(dead))
                + f'         ram (rw) : ORIGIN = {HEAP:#x}, LENGTH = 0x2000 }}\n'
                'SECTIONS {\n  .text : { ' + gap_text
                + ('} > gap\n  .hbss (NOLOAD) : { ' + bss + ' . = ALIGN(8); mpe_bss_end = .; } > ram\n'
                   if heap_bss else bss + ' } > gap\n')
                + ''.join(f'  .dead{i} : {{ {" ".join(dead_in[i])} }} > dead{i}\n' for i in range(len(dead)))
                + '  /DISCARD/ : { *(.comment) *(.ARM.attributes) *(.note*) *(.iplt) *(.rel.iplt) *(.igot.plt) }\n}\n')
        for name, addr in SYMBOLS.items():
            f.write(f'{name} = {addr:#x};\n')
    subprocess.run(['arm-none-eabi-ld', *(['--orphan-handling=error'] if dead else []),
                    '-T', ld, *objs, '-o', elf], check=True)
    sects = subprocess.run(['arm-none-eabi-objdump', '-h', elf], check=True, capture_output=True, text=True).stdout
    assert '.data' not in sects and '.bss' not in sects, 'variables hors des sections prévues'
    subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', '-j', '.text', elf, binf], check=True)
    spill = []                                           # (address, bytes) for each dead range used
    for i, (a, _) in enumerate(dead):
        part = os.path.join(out, f'patch.dead{i}.bin')
        subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', '-j', f'.dead{i}', elf, part], check=True)
        if os.path.exists(part) and os.path.getsize(part):
            spill.append((a, open(part, 'rb').read()))
    syms = {}
    for line in subprocess.run(['arm-none-eabi-nm', elf], check=True, capture_output=True, text=True).stdout.split('\n'):
        p = line.split()
        if len(p) == 3:
            syms[p[2]] = int(p[0], 16)
    with open(os.path.join(out, 'patch.lst'), 'w') as f:
        f.write(subprocess.run(['arm-none-eabi-objdump', '-d', elf], check=True, capture_output=True, text=True).stdout)
    return open(binf, 'rb').read(), syms, spill


def main(name):
    spec = PALIERS[name]
    out = os.path.join(ROOT, 'build', name)
    os.makedirs(out, exist_ok=True)
    heap_bss, dead = spec.get('heap_bss', False), spec.get('dead', ())
    blob, syms, spill = compile_and_link([os.path.join(HERE, f) for f in spec['sources']], out, heap_bss, dead,
                                         spec.get('force_dead', ()))
    blob += b'\0' * (-len(blob) % 8)                    # zero fill uses 8-byte stores
    assert CODE_END + len(blob) <= GAP_END, f'patch trop gros : {len(blob):#x} octets'
    code = bytearray(open(os.path.join(ROOT, 'ghidra', 'bin', 'unpacked', 'img1_CODE_c0000000.bin'), 'rb').read())
    assert len(code) == CODE_END - BASE, 'CODE inattendu'
    for addr, words in spec.get('checks', []):           # firmware words our C code relies on
        for i, v in enumerate(words):
            assert word(code, addr + 4 * i) == v, f'{addr + 4 * i:#x}: {word(code, addr + 4 * i):#x} != attendu {v:#x}'
    sites = [e[0] for k in ('data', 'calls', 'ptrs', 'branches') for e in spec.get(k, [])]
    for a, b in dead:
        assert not any(a <= s < b for s in sites), f'mot modifié dans la zone morte {a:#x}'
    for a, part in spill:                                # overwrite the dead ranges we use
        code[a - BASE:a - BASE + len(part)] = part
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
    print(f'{name}: {len(blob):#x} octets en {CODE_END:#x}'
          + ''.join(f' + {len(p):#x} en {a:#x}' for a, p in spill) + ' ; '
          + ', '.join(f'{k}={syms[k]:#x}' for k in sorted(ours)))


if __name__ == '__main__':
    main(sys.argv[1])
