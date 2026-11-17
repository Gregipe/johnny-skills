#!/usr/bin/env python3
"""Decode a paletted (8-bit colormap) PNG and print its dominant non-white colors.

Useful for extracting brand colors from a logo without PIL (which is often broken on
Greg's Mac due to an arm64/x86_64 mismatch). Handles PNG filter types 0 (None), 1 (Sub),
and 2 (Up) — enough for almost all logo images.

Usage: python3 logo_palette.py <logo.png>
"""
import struct, zlib, collections, sys


def decode_palette_png(path):
    data = open(path, "rb").read()
    pos = 8
    pal, idat, w, h = None, b"", None, None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h = struct.unpack(">II", chunk[:8])
        elif typ == b"PLTE":
            pal = chunk
        elif typ == b"IDAT":
            idat += chunk
        pos += 12 + ln
    raw = zlib.decompress(idat)
    stride = w + 1
    rows = []
    for y in range(h):
        f = raw[y * stride]
        row = list(raw[y * stride + 1:(y + 1) * stride])
        if f == 1:  # Sub
            for i in range(1, w):
                row[i] = (row[i] + row[i - 1]) % 256
        elif f == 2:  # Up
            prev = rows[-1] if rows else [0] * w
            for i in range(w):
                row[i] = (row[i] + prev[i]) % 256
        # filters 3 (Average) and 4 (Paeth) omitted — add if a logo uses them
        rows.append(row)
    c = collections.Counter()
    for row in rows:
        for idx in row:
            r, g, b = pal[idx * 3:idx * 3 + 3]
            if not (r > 240 and g > 240 and b > 240):  # skip white/transparent-ish
                c[(r, g, b)] += 1
    return c


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "logo.png"
    c = decode_palette_png(path)
    print("top non-white colors:")
    for (r, g, b), n in c.most_common(10):
        print(f"  #{r:02x}{g:02x}{b:02x}  x{n}")
