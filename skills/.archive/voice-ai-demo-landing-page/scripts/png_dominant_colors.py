#!/usr/bin/env python3
"""Dominant colors in a PNG — pure stdlib, no PIL.

Useful for brand extraction when PIL is unavailable or arch-mismatched
(x86_64 vs arm64). Handles 8-bit paletted (colortype 3) and 8-bit RGBA /
truecolor (colortype 6 / 2) PNGs with standard filter types 0-4.

Usage: python3 png_dominant_colors.py image.png [top_n]
"""
import struct, zlib, collections, sys


def _chunks(data):
    pos = 8
    while pos < len(data):
        ln = struct.unpack('>I', data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        yield typ, chunk
        pos += 12 + ln


def decode_png(path):
    data = open(path, 'rb').read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'not a PNG'
    w = h = bitdepth = colortype = None
    pal = None
    idat = b''
    for typ, chunk in _chunks(data):
        if typ == b'IHDR':
            w, h, bitdepth, colortype, _c, _i, _f = struct.unpack('>IIBBBBB', chunk)
        elif typ == b'PLTE':
            pal = chunk
        elif typ == b'IDAT':
            idat += chunk
        elif typ == b'IEND':
            break

    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colortype, 3)
    raw = zlib.decompress(idat)
    stride = w * bpp
    out = bytearray()
    prev = bytearray(stride)
    pos = 0

    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)

    for _y in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + paeth(a, b, c)) & 255
        out += line
        prev = line

    pixels = []
    for i in range(0, len(out), bpp):
        if colortype == 3:
            idx = out[i]
            r, g, b = pal[idx * 3:idx * 3 + 3]
            a = 255
        else:
            r, g, b = out[i], out[i + 1], out[i + 2]
            a = out[i + 3] if bpp == 4 else 255
        pixels.append((r, g, b, a))
    return pixels


def dominant(path, top_n=8, skip_white=True):
    c = collections.Counter()
    for r, g, b, a in decode_png(path):
        if a < 128:
            continue
        if skip_white and r > 240 and g > 240 and b > 240:
            continue
        c[(r, g, b)] += 1
    return c.most_common(top_n)


if __name__ == '__main__':
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    for (r, g, b), count in dominant(path, n):
        print(f'  #{r:02x}{g:02x}{b:02x}  x{count}')
