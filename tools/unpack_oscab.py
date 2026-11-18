"""Unpack a Nord OS update image (os.cab): section table + LZO1X-compressed CODE.

usage: python3 -I unpack_oscab.py os.cab outdir

Layout (big-endian), worked out from the Lead 4 OS 1.32 file:
  0x00  u32 header size (0x20), u32 end of image 1, u32 start of image 2, u32 size of image 2
  image header: u32 0x00xx0100, u32 ?, u32 0x00640000, u32 0, u32 section count,
  then per section 0x2c bytes: tag[4], offset, size, load address, crc, packed size (0 = stored), packed crc, ...
  Each section payload starts with 0x20 zero bytes; a CODE payload is LZO1X after those.
"""
import os, struct, sys, zlib


def lzo1x_decompress(src, pos=0):
    """Plain LZO1X decompressor (same state machine as minilzo's lzo1x_decompress)."""
    out = bytearray()
    ip = pos

    def ext(t, base):
        nonlocal ip
        while src[ip] == 0:
            t += 255
            ip += 1
        t += base + src[ip]
        ip += 1
        return t

    def copy(dist, n):
        start = len(out) - dist
        if start < 0:
            raise ValueError(f'back-reference before start at input {ip:#x}')
        for i in range(n):  # byte-wise: matches may overlap their own output
            out.append(out[start + i])

    state = 'loop'
    t = 0
    if src[ip] > 17:
        t = src[ip] - 17
        ip += 1
        out += src[ip:ip + t]
        ip += t
        state = 'match_next_lit' if t < 4 else 'first_literal_run'
    while True:
        if ip >= len(src):  # Nord streams carry no LZO end marker: they stop at the packed size
            return bytes(out), ip
        if state == 'loop':
            t = src[ip]; ip += 1
            if t >= 16:
                state = 'match'
                continue
            if t == 0:
                t = ext(0, 15)
            out += src[ip:ip + t + 3]
            ip += t + 3
            state = 'first_literal_run'
        if state == 'first_literal_run':
            t = src[ip]; ip += 1
            if t >= 16:
                state = 'match'
            else:
                d = 1 + 0x0800 + (t >> 2) + (src[ip] << 2); ip += 1
                copy(d, 3)
                state = 'match_done'
        if state == 'match_next_lit':
            out += src[ip:ip + t]; ip += t
            t = src[ip]; ip += 1
            state = 'match'
        if state == 'match':
            if t >= 64:  # M2
                d = 1 + ((t >> 2) & 7) + (src[ip] << 3); ip += 1
                copy(d, (t >> 5) - 1 + 2)
            elif t >= 32:  # M3
                n = t & 31
                if n == 0:
                    n = ext(0, 31)
                d = 1 + (src[ip] >> 2) + (src[ip + 1] << 6); ip += 2
                copy(d, n + 2)
            elif t >= 16:  # M4
                n = t & 7
                if n == 0:
                    n = ext(0, 7)
                d = ((t & 8) << 11) + (src[ip] >> 2) + (src[ip + 1] << 6); ip += 2
                if d == 0:
                    return bytes(out), ip  # end-of-stream marker
                copy(d + 0x4000, n + 2)
            else:  # M1
                d = 1 + (t >> 2) + (src[ip] << 2); ip += 1
                copy(d, 2)
            state = 'match_done'
        if state == 'match_done':
            t = src[ip - 2] & 3
            if t == 0:
                state = 'loop'
            else:
                state = 'match_next_lit'


def sections(b, start):
    """An image is a 0x20-byte preamble then its header; section offsets count from the image start."""
    hdr = struct.unpack_from('>5I', b, start + 0x20)
    for i in range(hdr[4]):
        o = start + 0x20 + 0x14 + i * 0x2c
        tag = b[o:o + 4].decode('ascii')
        off, size, addr, crc, psize, pcrc = struct.unpack_from('>6I', b, o + 4)
        yield tag, start + off, size, addr, crc, psize, pcrc


def main(path, outdir):
    b = open(path, 'rb').read()
    os.makedirs(outdir, exist_ok=True)
    _, end1, _, _ = struct.unpack_from('>4I', b, 0)
    for img, base in ((1, 0), (2, end1)):
        for tag, off, size, addr, crc, psize, pcrc in sections(b, base):
            raw = b[off:off + (psize or size)]
            if psize:
                assert raw[:0x20] == bytes(0x20), 'expected 0x20 zero bytes before the stream'
                data, end = lzo1x_decompress(raw, 0x20)
                # keep the payload's 0x20-byte zero prefix, as stored sections do
                # shortcut: image 1 decodes 1 byte past its size (last literal run); trimmed to the declared size
                data = (bytes(0x20) + data)[:size]
            else:
                data = raw
            name = f'img{img}_{tag}_{addr:08x}.bin'
            open(os.path.join(outdir, name), 'wb').write(data)
            ok = 'OK' if len(data) == size else f'TAILLE {len(data):#x} != {size:#x}'
            print(f'image {img} {tag} @ {addr:#010x}: {len(data):#x} octets ({ok})'
                  f' crc32={zlib.crc32(data):08x} attendu? {crc:08x}'
                  + (f' | flux crc32={zlib.crc32(raw):08x} attendu? {pcrc:08x}' if psize else ''))


if __name__ == '__main__':
    main(*sys.argv[1:3])
