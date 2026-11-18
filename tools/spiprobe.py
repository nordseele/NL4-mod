"""usage: python3 -I tools/spiprobe.py /dev/cu.usbmodemXXXX
Read-only SPI flash probe over the serprog protocol (pico-serprog). Sends only read opcodes."""
import os, sys, termios, tty, time

dev = sys.argv[1]
fd = os.open(dev, os.O_RDWR | os.O_NOCTTY)
tty.setraw(fd)

def rd(n, timeout=3.0):
    out, t0 = b'', time.time()
    while len(out) < n and time.time() - t0 < timeout:
        try:
            chunk = os.read(fd, n - len(out))
        except BlockingIOError:
            chunk = b''
        out += chunk
    return out

def spiop(w, rlen):
    assert w[0] in READ_ONLY, hex(w[0])  # never send anything but read opcodes
    os.write(fd, bytes([0x13]) + len(w).to_bytes(3, 'little') + rlen.to_bytes(3, 'little') + bytes(w))
    ack = rd(1)
    assert ack == b'\x06', ack
    return rd(rlen)

READ_ONLY = {0x9F, 0x05, 0x70, 0xB5, 0x85, 0x65, 0x03, 0x0B, 0x5A}

os.write(fd, b'\x00')  # NOP
print('nop', rd(1))
print('RDID   9F', spiop([0x9F], 20).hex(' '))
print('RDSR   05', spiop([0x05], 2).hex(' '))
print('RFSR   70', spiop([0x70], 2).hex(' '))
print('RDNVCR B5', spiop([0xB5], 2).hex(' '))
print('RDVCR  85', spiop([0x85], 1).hex(' '))
print('RDVECR 65', spiop([0x65], 1).hex(' '))
for a in (0x000000, 0x000100, 0x010000, 0x100000, 0x200000, 0x3F0000, 0x3FFF00):
    ad = [a >> 16 & 0xFF, a >> 8 & 0xFF, a & 0xFF]
    print(f'READ 03 {a:06x}', spiop([0x03] + ad, 32).hex(' '))
    print(f'FAST 0B {a:06x}', spiop([0x0B] + ad + [0], 32).hex(' '))
print('SFDP 5A', spiop([0x5A, 0, 0, 0, 0], 16).hex(' '))
