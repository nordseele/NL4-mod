"""Rebuild a Nord OS update file (os.cab) with replaced sections in image 1 (the OS).

usage: python3 -I tools/pack_oscab.py ORIGINAL.cab OUT.cab [TAG=FILE ...]
       python3 -I tools/pack_oscab.py --selftest
  e.g. CODE=ghidra/bin/unpacked/img1_CODE_c0000000.bin SRAM=my_sram.bin
With LZO1X-999 (python-lzo, e.g. in a throwaway container):
  docker run --rm -v "$PWD":/w -w /w ubuntu:22.04 bash -c 'apt-get update -qq &&
    apt-get install -y -qq python3-lzo >/dev/null && python3 -I tools/pack_oscab.py ...'
Without it, a pure-Python LZO1X-1 is used (about 220 KB bigger than Nord's CODE stream).

Image 2 (factory test program) is copied unchanged. For image 1, each section is taken
from FILE if given, else from the original; sections stored LZO1X-compressed in the
original are recompressed (LZO1X-1, with end marker), stored ones stay raw. Sections
are laid out back to back after the 0x2d4-byte header, as Nord does.

Checks the Mac updater makes (Nord OS Update, CBinFile::Verify / CBinHeader::Verify),
all reproduced here:
  cab header: (offset, size) per image, no overlap
  image header (0x2d4 bytes): u16 version, u8 type (1), u8, u16 build,
      u16 checksum = ~(byte sum of header[8:0x2d4]) & 0xffff, u32 start, u32, u32 count,
      16 section slots of 0x2c bytes (tag, offset, size, addr, crc, psize, pcrc, 4 x u32)
  section: crc = ~(byte sum of data), pcrc = ~(byte sum of packed bytes); the updater
      compares the low 16 bits of the one it sends (pcrc if packed, else crc).
The output is verified by decompressing it again with tools/unpack_oscab.py's decoder.
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unpack_oscab import lzo1x_decompress, sections  # noqa: E402

HDR = 0x2d4
nsum = lambda x: (~sum(x)) & 0xffffffff


def lzo1x_1_compress(src):
    """LZO1X-1 compressor (port of minilzo's lzo1x_1_compress: 48 KiB blocks, 14-bit dict)."""
    out = bytearray()
    n = len(src)

    def literals(lit, final=False):
        t = len(lit)
        if t == 0:
            return
        if final and not out and t <= 238:
            out.append(17 + t)
        elif t <= 3:
            out[-2] |= t  # stored in the low bits of the previous match
        elif t <= 18:
            out.append(t - 3)
        else:
            tt = t - 18
            out.append(0)
            while tt > 255:
                tt -= 255
                out.append(0)
            out.append(tt)
        out.extend(lit)

    pos = 0          # start of the pending literals (may lie in an earlier block)
    blk = 0
    while n - blk > 20:
        ll = min(n - blk, 49152)
        ip_end = blk + ll - 20
        d = [0] * (1 << 14)                         # dict holds offsets from the block start
        ip = blk + max(0, 4 - (blk - pos))
        step = True                                 # minilzo: 'literal' label (skip ahead)
        while True:
            if step:
                ip += 1 + ((ip - max(pos, blk)) >> 5)
            step = True
            if ip >= ip_end:
                break
            dv = src[ip] | src[ip + 1] << 8 | src[ip + 2] << 16 | src[ip + 3] << 24
            di = ((0x1824429d * dv) & 0xffffffff) >> 18
            m_pos = blk + d[di]
            d[di] = ip - blk
            if m_pos >= ip or src[m_pos:m_pos + 4] != src[ip:ip + 4]:
                continue
            literals(src[pos:ip])
            m_len = 4
            while ip + m_len < ip_end and src[ip + m_len] == src[m_pos + m_len]:
                m_len += 1
            m_off = ip - m_pos
            ip += m_len
            pos = ip
            step = False                            # minilzo: 'goto next' after a match
            if m_len <= 8 and m_off <= 0x800:            # M2
                m_off -= 1
                out += bytes(((m_len - 1) << 5 | (m_off & 7) << 2, m_off >> 3))
            elif m_off <= 0x4000:                          # M3
                m_off -= 1
                if m_len <= 33:
                    out.append(32 | (m_len - 2))
                else:
                    m_len -= 33
                    out.append(32)
                    while m_len > 255:
                        m_len -= 255
                        out.append(0)
                    out.append(m_len)
                out += bytes(((m_off << 2) & 0xff, (m_off >> 6) & 0xff))
            else:                                          # M4
                m_off -= 0x4000
                if m_len <= 9:
                    out.append(16 | ((m_off >> 11) & 8) | (m_len - 2))
                else:
                    m_len -= 9
                    out.append(16 | ((m_off >> 11) & 8))
                    while m_len > 255:
                        m_len -= 255
                        out.append(0)
                    out.append(m_len)
                out += bytes(((m_off << 2) & 0xff, (m_off >> 6) & 0xff))
        blk += ll
    literals(src[pos:], final=True)
    out += b'\x11\x00\x00'                               # end of stream (M4, distance 0)
    return bytes(out)


def compress(data):
    """LZO1X-999 through python-lzo when present (smaller than Nord's own stream), else LZO1X-1."""
    try:
        import lzo
    except ImportError:
        print('python-lzo absent : LZO1X-1 en Python (plus gros, ~+220 Ko pour le CODE)')
        return lzo1x_1_compress(data)
    return lzo.compress(data, 9, False)


def build_image(img, repl):
    """Rebuild one image (header + sections) with replacement payloads {tag: bytes}."""
    hdr = bytearray(img[:HDR])
    secs = list(sections(img, -0x20))                    # offsets relative to img[0]
    off = HDR
    body = bytearray()
    for i, (tag, o, size, addr, crc, psize, pcrc) in enumerate(secs):
        if tag in repl:
            data = repl.pop(tag)
        else:
            raw = img[o:o + (psize or size)]
            data = lzo1x_decompress(raw)[0] if psize else raw
        packed = compress(data) if psize else b''
        stored = packed or data
        slot = 0x14 + i * 0x2c
        struct.pack_into('>6I', hdr, slot + 4, off, len(data), addr, nsum(data),
                         len(packed), nsum(packed) if packed else 0)
        body += stored
        off += len(stored)
    if repl:
        raise SystemExit(f'unknown section(s): {", ".join(repl)}')
    struct.pack_into('>H', hdr, 6, (~sum(hdr[8:HDR])) & 0xffff)
    return bytes(hdr + body)


def check(cab):
    """Re-read the file the way the updater and the keyboard do; raise on any mismatch."""
    o1, s1, o2, s2 = struct.unpack_from('>4I', cab, 0)
    assert o1 == 0x20 and o2 == o1 + s1 and o2 + s2 == len(cab), 'cab header'
    for base in (o1, o2):
        h = cab[base:base + HDR]
        assert h[2] == 1, 'image type'
        assert struct.unpack_from('>H', h, 6)[0] == (~sum(h[8:HDR])) & 0xffff, 'header checksum'
        for tag, o, size, addr, crc, psize, pcrc in sections(cab, base - 0x20):
            raw = cab[o:o + (psize or size)]
            data = lzo1x_decompress(raw)[0] if psize else raw
            assert len(data) == size and nsum(data) == crc, f'{tag} size/crc'
            assert not psize or nsum(raw) == pcrc, f'{tag} packed crc'


def main(orig, out, *args):
    cab = open(orig, 'rb').read()
    o1, s1, o2, s2 = struct.unpack_from('>4I', cab, 0)
    repl = {}
    for a in args:
        tag, path = a.split('=', 1)
        repl[tag] = open(path, 'rb').read()
    img1 = build_image(cab[o1:o1 + s1], repl)
    img2 = cab[o2:o2 + s2]
    new = struct.pack('>8I', 0x20, len(img1), 0x20 + len(img1), len(img2), 0, 0, 0, 0) + img1 + img2
    check(new)
    open(out, 'wb').write(new)
    print(f'{out}: {len(new)} octets (original {len(cab)}), image 1 {len(img1):#x}, vérifié')


def selftest():
    """Round-trip small and edge-case inputs through the Python compressor and decoder."""
    for n in (0, 1, 3, 5, 17, 21, 100, 5000, 120000):
        for data in (bytes(n), os.urandom(n), (b'abcabcab' * (n // 8 + 1))[:n]):
            assert lzo1x_decompress(lzo1x_1_compress(data))[0] == data, n
    print('selftest OK')


if __name__ == '__main__':
    selftest() if sys.argv[1:] == ['--selftest'] else main(*sys.argv[1:])
