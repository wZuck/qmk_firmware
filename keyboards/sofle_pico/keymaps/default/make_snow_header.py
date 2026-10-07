#!/usr/bin/env python3
"""Turn the four `snow_*.png` into `oled_snow.h`.

`snow_1.png` / `snow_2.png` and their `_inv` twins are produced by
`make_snow.py`; this step packs them into the two frame tables the firmware
draws from, in the same page format as the animation library:

    oled_snow      SOFLE_SNOW_FRAMES       the pair, lit on a dark panel
    oled_snow_inv  SOFLE_SNOW_FRAMES       the same pair, dark on a lit panel

    python3 make_snow_header.py           # writes oled_snow.h next to itself

Both tables are the same drawing at both polarities, so the firmware can offer
"normal" and "inverted" screens without storing the picture twice in any other
sense. The packing is `img2c.py`'s job - this only adds the wrapper, because
img2c.py emits a single flat array and an animation frame has to carry the
frame index.

Needs no third-party packages: `img2c.py` is pure stdlib.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "oled_snow.h")
IMG2C = os.path.join(HERE, "img2c.py")

SOURCES = ("snow_1", "snow_2")


def pack(name):
    """One PNG -> the 1024 bytes of a whole 64x128 canvas, via img2c.py.

    img2c.py packs a pixel as a lit bit (1) when the PNG sample is >= 128, so a
    black-on-white drawing comes out as a lit *background* with a dark figure.
    That is the opposite of how the animation library draws and of what the
    normal/inverted screens should mean, so the bytes are flipped here: in this
    header a set bit is a lit pixel of the drawing, exactly like oled_anim.h.
    """
    png = os.path.join(HERE, name + ".png")
    if not os.path.exists(png):
        sys.exit("missing %s - run make_snow.py first" % png)
    tmp = os.path.join(HERE, ".%s.h" % name)
    subprocess.run([sys.executable, IMG2C, png, "--height", "128", "--name", name, "-o", tmp],
                   check=True, stdout=subprocess.DEVNULL)
    text = open(tmp).read()
    os.remove(tmp)
    start = text.index("{")
    end = text.index("};")
    vals = [int(v, 16) for v in re.findall(r"0x([0-9a-fA-F]{2})", text[start:end])]
    if len(vals) != 1024:
        sys.exit("%s packed to %d bytes, expected 1024" % (name, len(vals)))
    return [v ^ 0xFF for v in vals]


def emit(fh, cname, frames, count_macro):
    fh.write("static const char PROGMEM %s[%s][1024] = {\n" % (cname, count_macro))
    for i, data in enumerate(frames):
        fh.write("    { // frame %d\n" % i)
        for k in range(0, len(data), 16):
            fh.write("        " + ",".join("0x%02x" % b for b in data[k:k + 16]) + ",\n")
        fh.write("    },\n")
    fh.write("};\n\n")


def main():
    normal = [pack(n) for n in SOURCES]
    inverted = [pack(n + "_inv") for n in SOURCES]

    for i, (a, b) in enumerate(zip(normal, inverted)):
        flipped = [(255 - v) for v in a]
        if b != flipped:
            sys.exit("frame %d: the _inv PNG is not a pixel-flip of the normal one" % i)

    with open(OUT, "w") as fh:
        fh.write("// Generated from snow_*.png by make_snow_header.py - do not edit by hand.\n")
        fh.write("//\n")
        fh.write("// The two `oled_snow*.pdf` drawings of the snowboarding pair, in two polarities:\n")
        fh.write("//\n")
        fh.write("//   oled_snow      frame 0 arm down, frame 1 arm up in a peace sign\n")
        fh.write("//                  (lit snowboarders on a dark panel - the night screen)\n")
        fh.write("//   oled_snow_inv  the same two frames with every pixel flipped\n")
        fh.write("//                  (dark snowboarders on a lit panel - the day screen)\n")
        fh.write("//\n")
        fh.write("// %d frames of 64x128 px, 1024 bytes each. Same page format as oled_anim.h, so\n"
                 % (len(normal) * 2))
        fh.write("// they go through oled_write_raw_P() untouched.\n")
        fh.write("//\n")
        fh.write("// Drawings are landscape and the canvas is portrait, so the pair sits in the\n")
        fh.write("// middle rows (33-94) with blank bands above and below; there is nothing in\n")
        fh.write("// the source to put there. Regenerate with `make_snow.py` then this script.\n")
        fh.write("#pragma once\n\n")
        fh.write("#define SOFLE_SNOW_FRAMES %d\n\n" % len(normal))
        emit(fh, "oled_snow", normal, "SOFLE_SNOW_FRAMES")
        emit(fh, "oled_snow_inv", inverted, "SOFLE_SNOW_FRAMES")

    print("wrote %s" % OUT)
    print("  oled_snow / oled_snow_inv: %d frames each, %d bytes total"
          % (len(normal), len(normal) * 2 * 1024))
    for i, (data, inv) in enumerate(zip(normal, inverted)):
        print("  frame %d: %d lit px normal, %d lit px inverted"
              % (i, sum(bin(b).count("1") for b in data), sum(bin(b).count("1") for b in inv)))


if __name__ == "__main__":
    main()
