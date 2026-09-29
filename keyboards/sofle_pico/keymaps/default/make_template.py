#!/usr/bin/env python3
"""Generate the drawing templates for the right half's OLED canvas.

Two files, both a plain black canvas with magenta guides:

  oled_template.png     the canvas at 4x, so there are pixels to actually draw
  oled_template_1x.png  the same canvas at 1:1, for pixel-exact work

The guides mark the 8 px pages the driver writes in and the 16 px columns, so
you can see where the hardware boundaries fall. They are hairlines - thinner
than one canvas pixel at 4x - so a 4:1 reduction averages them away and they
never reach the panel. Drawing over them, or leaving them, makes no difference.

Convert the finished drawing with img2c.py; see readme.md. Pure stdlib.
"""

import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))

W, H = 64, 128          # canvas, in OLED pixels
MAGENTA = (255, 0, 255)
HAIRLINE = 2            # device px, at 4x


def png_rgb(path, w, h, rows):
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    with open(path, "wb") as fh:
        fh.write(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )


def template(scale):
    """A black canvas at `scale`, with the guide grid drawn if it would show."""
    w, h = W * scale, H * scale
    img = [[(0, 0, 0)] * w for _ in range(h)]

    if scale > 1:
        def mag(y, x):
            if 0 <= y < h and 0 <= x < w:
                img[y][x] = MAGENTA

        # Interior boundaries only - the canvas edge already marks the outer
        # ones, and a hairline there would sit half off the image.
        for x in range(16, W, 16):
            for dx in range(HAIRLINE):
                for y in range(h):
                    mag(y, x * scale + dx)
        for y in range(8, H, 8):
            for dy in range(HAIRLINE):
                for x in range(w):
                    mag(y * scale + dy, x)

    return w, h, img


def main():
    for scale, name in ((4, "oled_template.png"), (1, "oled_template_1x.png")):
        w, h, img = template(scale)
        path = os.path.join(HERE, name)
        png_rgb(path, w, h, img)
        print("wrote %s (%dx%d, %d:1 of %dx%d)" % (path, w, h, scale, W, H))


if __name__ == "__main__":
    main()
