#!/usr/bin/env python3
"""Turn a PNG into a 1-bit bitmap in SSD1306 page format for a QMK OLED.

Draw on `oled_template.png` - the 64 x 96 canvas at 4x, so there is room to
work - then run this on the result:

    python3 img2c.py my_picture.png --helper-color ff00ff -o oled_image.h

The sofle_pico OLEDs run at a rotation that gives each half a 64 x 128 portrait
canvas. The picture occupies the top `height` px (a multiple of 8) and the
status text the lines below it, so `--height` has to stay in sync with
`SOFLE_OLED_IMAGE_HEIGHT` in keymap.c. The width is fixed at 64 by the
rotation, so leave `--width` alone.

The array goes into the display buffer through `oled_write_raw_P()`, so it has
to be generated at exactly the size the firmware expects.

Only the Python standard library is used; there is nothing to pip install.
"""

import argparse
import struct
import sys
import zlib

# --------------------------------------------------------------------------
# PNG decoding
# --------------------------------------------------------------------------

_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}  # gray, rgb, palette, gray+a, rgba


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(raw, height, bpp, stride):
    """Undo the per-scanline PNG filters, returning the raw sample bytes.

    `bpp` is the filter offset (bytes per pixel, never less than 1) while
    `stride` is the real scanline length - the two differ for bit depths
    below 8, where several pixels share a byte.
    """
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(a, prev[i], c)) & 0xFF
        elif ftype != 0:
            raise ValueError("unknown PNG filter type %d on row %d" % (ftype, y))
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return out


def _unpack_subbyte(line, count, bitdepth):
    """Expand 1/2/4-bit samples into one value per sample (no scaling)."""
    per_byte = 8 // bitdepth
    mask = (1 << bitdepth) - 1
    vals = []
    for i in range(count):
        byte = line[i // per_byte]
        shift = 8 - bitdepth * (i % per_byte + 1)
        vals.append((byte >> shift) & mask)
    return vals


def _to_luma_alpha(ctype, bitdepth, plte, trns, line, width, helper=None):
    """Decode one scanline into a list of (luma, alpha) pairs, both 0-255.

    `helper`, when given, is an (r, g, b, tolerance) tuple: any pixel close to
    that colour is made fully transparent. That is how the magenta guide grid in
    the drawing templates is dropped before the image gets resampled.
    """
    if bitdepth == 8:
        vals = list(line)
        scale = 1
    elif bitdepth == 16:
        vals = [(line[i] << 8) | line[i + 1] for i in range(0, len(line), 2)]
        scale = 1 / 257.0
    else:
        vals = _unpack_subbyte(line, width * _CHANNELS[ctype], bitdepth)
        scale = 255.0 / ((1 << bitdepth) - 1)

    px = []
    for x in range(width):
        if ctype == 0:  # grayscale
            r = g = b = int(vals[x] * scale)
            a = 255
        elif ctype == 4:  # grayscale + alpha
            r = g = b = int(vals[2 * x] * scale)
            a = int(vals[2 * x + 1] * scale)
        elif ctype == 2:  # rgb
            r, g, b = (int(vals[3 * x + i] * scale) for i in range(3))
            a = 255
        elif ctype == 6:  # rgba
            r, g, b = (int(vals[4 * x + i] * scale) for i in range(3))
            a = int(vals[4 * x + 3] * scale)
        else:  # palette
            idx = vals[x]
            r, g, b = plte[idx]
            a = trns[idx] if trns and idx < len(trns) else 255

        if helper is not None and _matches_helper(r, g, b, helper):
            px.append((0, 0))
        else:
            px.append((_luma(r, g, b), a))
    return px


def _matches_helper(r, g, b, helper):
    hr, hg, hb, tol = helper
    return abs(r - hr) <= tol and abs(g - hg) <= tol and abs(b - hb) <= tol


def _luma(r, g, b):
    return (299 * r + 587 * g + 114 * b) // 1000


def read_png(path, helper=None):
    """Return (width, height, rows) where each row is a list of (luma, alpha)."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s is not a PNG file" % path)

    pos = 8
    idat = bytearray()
    plte = trns = None
    ihdr = None
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length  # length + type + data + crc
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"PLTE":
            plte = [tuple(chunk[i : i + 3]) for i in range(0, len(chunk), 3)]
        elif ctype == b"tRNS":
            trns = list(chunk)
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break

    if ihdr is None:
        raise ValueError("%s has no IHDR chunk" % path)
    width, height, bitdepth, ctype, _comp, _filt, interlace = ihdr

    if interlace:
        raise ValueError(
            "%s is interlaced (Adam7), which this script does not handle.\n"
            "Re-save it without interlacing (e.g. `sips -s format png in.png --out out.png`,"
            " or untick \"Interlaced\" in your image editor)." % path
        )
    if ctype not in _CHANNELS:
        raise ValueError("%s uses unsupported PNG colour type %d" % (path, ctype))
    if bitdepth < 8 and _CHANNELS[ctype] != 1:
        raise ValueError("%s uses unsupported %d-bit colour" % (path, bitdepth))
    if ctype == 3 and plte is None:
        raise ValueError("%s is palette-based but has no PLTE chunk" % path)

    channels = _CHANNELS[ctype]
    bpp = max(1, channels * bitdepth // 8)
    stride = (width * channels * bitdepth + 7) // 8
    raw = zlib.decompress(bytes(idat))
    pixels = _unfilter(raw, height, bpp, stride)

    rows = []
    for y in range(height):
        line = pixels[y * stride : (y + 1) * stride]
        rows.append(_to_luma_alpha(ctype, bitdepth, plte, trns, line, width, helper))
    return width, height, rows


# --------------------------------------------------------------------------
# Image processing
# --------------------------------------------------------------------------


def resize(rows, sw, sh, dw, dh):
    """Area-average resample of (luma, alpha) pixels to (dw, dh).

    Samples are averaged weighted by their alpha, so a transparent sample is
    skipped rather than counted as black. That is what lets a helper colour
    (the guide grid in the drawing templates) be erased without leaving a dark
    scar: the pixel takes its value from whatever is drawn around it. A block
    with no opaque samples at all comes out black, which on these panels is the
    canvas colour anyway.

    At 1:1 this is an identity transform - the source pixel is copied through.
    """
    out = []
    for dy in range(dh):
        y0, y1 = dy * sh / dh, (dy + 1) * sh / dh
        line = []
        for dx in range(dw):
            x0, x1 = dx * sw / dw, (dx + 1) * sw / dw
            total = 0.0
            weight = 0.0
            for sy in range(int(y0), min(int(y1 - 1e-9) + 1, sh)):
                row = rows[sy]
                for sx in range(int(x0), min(int(x1 - 1e-9) + 1, sw)):
                    luma, alpha = row[sx]
                    if alpha:
                        w = alpha / 255.0
                        total += luma * w
                        weight += w
            line.append(int(round(total / weight)) if weight else 0)
        out.append(line)
    return out


def fit_to_canvas(rows, sw, sh, dw, dh, mode):
    """Map a source image onto a dw x dh canvas, returning a dw x dh grid."""
    if mode == "stretch":
        return resize(rows, sw, sh, dw, dh)

    src_ar, dst_ar = sw / sh, dw / dh
    if mode == "cover":
        # Crop the source to the canvas aspect ratio, then scale to fill it.
        if src_ar > dst_ar:
            keep_w = max(1, int(round(sh * dst_ar)))
            x0 = (sw - keep_w) // 2
            return resize([r[x0 : x0 + keep_w] for r in rows], keep_w, sh, dw, dh)
        keep_h = max(1, int(round(sw / dst_ar)))
        y0 = (sh - keep_h) // 2
        return resize(rows[y0 : y0 + keep_h], sw, keep_h, dw, dh)

    # contain: scale to fit inside the canvas, centre it, leave black bars.
    scale = min(dw / sw, dh / sh)
    tw, th = max(1, int(round(sw * scale))), max(1, int(round(sh * scale)))
    small = resize(rows, sw, sh, tw, th)
    canvas = [[0] * dw for _ in range(dh)]
    ox, oy = (dw - tw) // 2, (dh - th) // 2
    for y in range(th):
        canvas[oy + y][ox : ox + tw] = small[y]
    return canvas


def rotate(rows, degrees):
    """Rotate a list-of-rows by a multiple of 90 degrees."""
    if degrees == 0:
        return rows
    if degrees == 180:
        return [list(reversed(r)) for r in reversed(rows)]
    if degrees == 90:  # clockwise
        return [list(r) for r in zip(*reversed(rows))]
    if degrees == 270:  # counter-clockwise
        return [list(r) for r in reversed(list(zip(*rows)))]
    raise ValueError("rotation must be one of 0/90/180/270")


def threshold(gray, w, h, level):
    return [1 if v >= level else 0 for v in gray]


def dither(gray, w, h):
    """Floyd-Steinberg, which keeps gradients readable on a 1-bit panel."""
    buf = [float(v) for v in gray]
    out = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            old = buf[i]
            new = 255.0 if old > 127.0 else 0.0
            out[i] = 1 if new else 0
            err = old - new
            if x + 1 < w:
                buf[i + 1] += err * 7 / 16
            if y + 1 < h:
                if x > 0:
                    buf[i + w - 1] += err * 3 / 16
                buf[i + w] += err * 5 / 16
                if x + 1 < w:
                    buf[i + w + 1] += err * 1 / 16
    return out


def pack_page_format(bits, w, h):
    """Pack 1-bit pixels into SSD1306 page format (one byte = 8 vertical px)."""
    buf = bytearray()
    for page in range(h // 8):
        for x in range(w):
            byte = 0
            for bit in range(8):
                if bits[(page * 8 + bit) * w + x]:
                    byte |= 1 << bit
            buf.append(byte)
    return buf


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("png", help="input PNG")
    ap.add_argument("-o", "--output", default="oled_image.h", help="output header (default: oled_image.h)")
    ap.add_argument("--name", default="oled_image", help="C array name (default: oled_image)")
    ap.add_argument("--width", type=int, default=64, help="canvas width in px (default: 64)")
    ap.add_argument("--height", type=int, default=96, help="image height in px, multiple of 8 (default: 96)")
    ap.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270],
                    help="rotate the source before packing; use 180 if it comes out upside down")
    ap.add_argument("--dither", action="store_true", help="Floyd-Steinberg instead of a hard threshold")
    ap.add_argument("--threshold", type=int, default=128, help="cutoff for the non-dither path (default: 128)")
    ap.add_argument("--invert", action="store_true", help="swap black and white")
    ap.add_argument("--fit", choices=["stretch", "contain", "cover"], default="contain",
                    help="how to map the source aspect ratio onto the canvas (default: contain)")
    ap.add_argument("--helper-color", metavar="RRGGBB",
                    help="treat pixels of this colour as background; clears the magenta guide "
                         "grid in the drawing templates")
    ap.add_argument("--helper-tolerance", type=int, default=60, metavar="N",
                    help="how far a pixel may stray from --helper-color and still match (default: 60)")
    args = ap.parse_args()

    if args.height % 8:
        sys.exit("error: --height must be a multiple of 8, got %d" % args.height)

    helper = None
    if args.helper_color:
        rgb = args.helper_color.lstrip("#")
        if len(rgb) != 6:
            sys.exit("error: --helper-color wants six hex digits, e.g. ff00ff")
        try:
            helper = tuple(int(rgb[i : i + 2], 16) for i in (0, 2, 4)) + (args.helper_tolerance,)
        except ValueError:
            sys.exit("error: --helper-color is not valid hex: %s" % args.helper_color)

    sw, sh, rows = read_png(args.png, helper)
    small = fit_to_canvas(rows, sw, sh, args.width, args.height, args.fit)
    flat = [v for row in small for v in row]
    flat = [255 - v if args.invert else v for v in flat]

    # Rotating after resampling keeps the aspect handling above simple.
    if args.rotate:
        grid = [flat[i * args.width : (i + 1) * args.width] for i in range(args.height)]
        grid = rotate(grid, args.rotate)
        flat = [v for row in grid for v in row]
        out_w, out_h = len(grid[0]), len(grid)
    else:
        out_w, out_h = args.width, args.height

    bits = dither(flat, out_w, out_h) if args.dither else threshold(flat, out_w, out_h, args.threshold)
    packed = pack_page_format(bits, out_w, out_h)

    with open(args.output, "w") as fh:
        fh.write("// Generated by img2c.py from %s - do not edit by hand.\n" % args.png)
        fh.write("// %dx%d px, %d bytes, SSD1306 page format.\n" % (out_w, out_h, len(packed)))
        fh.write("#pragma once\n\n")
        fh.write("static const char PROGMEM %s[] = {\n" % args.name)
        for i in range(0, len(packed), 16):
            fh.write("    " + ",".join("0x%02x" % b for b in packed[i : i + 16]) + ",\n")
        fh.write("};\n")

    lit = sum(bits)
    print("%s -> %s (%dx%d, %d bytes, %.1f%% of the pixels lit)"
          % (args.png, args.output, out_w, out_h, len(packed), 100.0 * lit / (out_w * out_h)))
    if not lit:
        print("warning: nothing is lit - the picture may have been scaled away, or every pixel\n"
              "         was stripped as --helper-color", file=sys.stderr)


if __name__ == "__main__":
    main()
