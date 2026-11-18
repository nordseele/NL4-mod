"""List tables of code pointers (vtables and similar) in the data part of a raw image.

usage: python3 -I find_ptr_tables.py code.bin base_hex code_end_hex > vtables.txt
Output lines: "table_addr count entry1 entry2 ...". A run of >= 6 aligned words that all
point into [base+0x20, code_end) counts as a table.
"""
import struct, sys

blob = open(sys.argv[1], 'rb').read()
base, end = int(sys.argv[2], 16), int(sys.argv[3], 16)
W = lambda off: struct.unpack_from('<I', blob, off)[0]
is_code = lambda v: base + 0x20 <= v < end and v % 4 == 0

i = end - base
while i < len(blob) - 4:
    n = 0
    while i + 4 * n < len(blob) - 3 and is_code(W(i + 4 * n)):
        n += 1
    if n >= 6:
        print(f'{base + i:#x} {n} ' + ' '.join(f'{W(i + 4 * k):x}' for k in range(n)))
        i += 4 * n
    else:
        i += 4
