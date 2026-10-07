#!/usr/bin/env python3
"""Generate oled_anim.h - the animation library for the OLEDs.

Every animation is an 8 frame, 64 x 128 loop of the same big-eyed character,
drawn from primitives (line / ellipse / disc) into a 1 bit grid and packed into
the SSD1306 page format the driver wants.

  0 bounce  hop, squash on landing, blink, arms swinging
  1 wave    standing still, one arm waving hello
  2 walk    marching in place, arms swinging the other way
  3 sleep   eyes shut, breathing slowly, z's drifting up

The character's proportions come from the reference drawing (ink box 114 x 120
px) scaled by 64/114, so the arms span the full 64 px canvas and the figure is
66 px tall - which leaves room for the hop. Pure stdlib.

Run from anywhere; it writes oled_anim.h next to itself.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
# .../keyboards/sofle_pico/keymaps/default -> the root of the QMK tree.
QMK = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.join(HERE, "oled_anim.h")
# The same loops with every pixel flipped, for the "inverted" screens the OLED
# key can switch to. Flipping the packed bytes is exactly flipping the pixels:
# the buffer is one bit per pixel whichever way the byte is read.
OUT_INV = os.path.join(HERE, "oled_anim_inv.h")

W, H = 64, 128
STROKE = 2
FRAMES = 8

# Figure geometry, in "figure" coordinates: origin on the body centre line,
# y grows downwards, y = 0 is the head's centre.
# Vectorised off the reference drawing - fit_reference.py finds the head/eye
# circles, the pupils and the body ellipse and prints them in this coordinate
# system (radii are to the middle of the stroke).
#
# One deliberate change: in the reference the eyes are as wide as the head, so
# at 64 px their outlines merge with the head's. The head is drawn a little
# bigger than measured (13.5 instead of 10.1) so both eyeballs sit clearly
# *inside* it while still being big, and the face reads at this size.
HEAD_CY, HEAD_R = 12.0, 13.5
EYE_DX, EYE_CY, EYE_R = 5.2, 10.0, 6.0
PUPIL_R, PUPIL_DX, PUPIL_DY = 2.8, 1.4, 0.5
BODY_CY, BODY_RX, BODY_RY = 34.5, 19.5, 23.9
ARM_X1, ARM_DY = 31.5, 0.0
LEG_DX, LEG_Y1 = 13.5, 66.75

BASE_TOP = 32       # where the figure's y = 0 sits when dy is 0
PIVOT_Y = BASE_TOP + 34.5   # rotation pivot: the middle of the body

# ---------------------------------------------------------------------------
# Animation parameters. Each list has FRAMES entries; the fields are:
#   dy      whole figure up (negative) / down (positive)
#   squash  +1 landed and flattened, -1 stretched in the air
#   rot     degrees of lean, positive = to the right
#   arm_l   how far the left arm's tip goes up (negative = down)
#   arm_r   the same for the right arm
#   lift_l  how far the left foot lifts off the ground
#   lift_r  the same for the right foot
#   blink   frames with the eyes shut
#   look    per frame pupil offset (dx, dy)
# ---------------------------------------------------------------------------

Z = (0, 0)

ANIMATIONS = [
    ("bounce", "hop, squash on landing, blink, arms swing",
     dict(
         dy=[0, -3, -9, -14, -16, -14, -9, -3],
         squash=[1.0, 0.5, -0.3, -1.0, -1.0, -0.3, 0.5, 1.0],
         arm_l=[0, 3, 5, 3, 0, -3, -5, -3],
         arm_r=[0, -3, -5, -3, 0, 3, 5, 3],
         blink={4, 5},
         look=[Z, (1, 0), (1, 0), (1, -1), (1, 0), (1, 0), Z, (-1, 0)],
     )),
    ("wave", "standing, waving one arm hello",
     dict(
         squash=[0, 0.2, 0.4, 0.2, 0, 0.2, 0.4, 0.2],
         arm_l=[0] * FRAMES,
         arm_r=[7, 12, 16, 12, 7, 12, 16, 12],
         blink={4},
         look=[(1, 0), (1, 0), (1, 0), (1, 0), (1, 0), (1, -1), (1, 0), (1, 0)],
     )),
    ("walk", "marching in place, arms swinging the other way",
     dict(
         dy=[0, -1, -3, -1, 0, -1, -3, -1],
         arm_l=[0, 3, 5, 3, 0, -3, -5, -3],
         arm_r=[0, -3, -5, -3, 0, 3, 5, 3],
         lift_l=[0, 5, 9, 5, 0, 0, 0, 0],
         lift_r=[0, 0, 0, 0, 0, 5, 9, 5],
         look=[Z, (0, 0), (0, -1), (0, 0), Z, (0, 0), (0, -1), (0, 0)],
     )),
    ("sleep", "eyes shut, breathing slowly, z's drifting up",
     dict(
         dy=[0, 0, 0, 0, 0, 0, 0, 0],
         squash=[0.35, 0.5, 0.6, 0.5, 0.35, 0.15, 0.05, 0.15],
         arm_l=[-3] * FRAMES,
         arm_r=[-3] * FRAMES,
         blink=set(range(FRAMES)),
         sleep_z=True,
     )),
]


def load_font():
    """The driver's 6x8 font: one byte per column, LSB is the top row."""
    src = open(os.path.join(QMK, "drivers", "oled", "glcdfont.c")).read()
    body = re.search(r"font\[\]\s*(?:PROGMEM\s*)?=\s*\{(.*?)\};", src, re.S).group(1)
    body = re.sub(r"//[^\n]*", "", body)  # trailing "// 0x4D M" comments are not data
    data = [int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", body)]
    assert len(data) % 6 == 0, "font table is not a whole number of glyphs"
    return data


FONT = load_font()


class Grid:
    def __init__(self):
        self.px = [[False] * W for _ in range(H)]
        self.rot = 0.0

    def plot_raw(self, x, y, thickness=STROKE, value=True):
        for dy in range(thickness):
            for dx in range(thickness):
                xi, yi = int(round(x)) + dx, int(round(y)) + dy
                if 0 <= xi < W and 0 <= yi < H:
                    self.px[yi][xi] = value

    def plot(self, x, y, thickness=STROKE, value=True):
        """Figure plotting: the whole character leans around PIVOT_Y."""
        if self.rot:
            import math

            a = math.radians(self.rot)
            cx, cy = W / 2.0, PIVOT_Y
            x, y = cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)
        self.plot_raw(x, y, thickness, value)

    def line(self, x0, y0, x1, y1, thickness=STROKE, value=True):
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.plot(x0, y0, thickness, value)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ellipse(self, cx, cy, rx, ry, thickness=STROKE, value=True, step_deg=0.25):
        import math

        for i in range(int(360 / step_deg)):
            t = math.radians(i * step_deg)
            self.plot(cx + rx * math.cos(t), cy + ry * math.sin(t), thickness, value)

    def fill_ellipse(self, cx, cy, rx, ry, value=False):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    self.plot(x, y, 1, value)

    def disc(self, cx, cy, r, value=True):
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.plot(x, y, 1, value)

    def glyph(self, ch, x0, y0, scale=2):
        """Blit one 6x8 font glyph, scaled and *not* affected by the lean."""
        cols = FONT[ord(ch) * 6 : ord(ch) * 6 + 6]
        for ci, col in enumerate(cols):
            for row in range(8):
                if col >> row & 1:
                    for dy in range(scale):
                        for dx in range(scale):
                            self.plot_raw(x0 + ci * scale + dx, y0 + row * scale + dy)


def frame(params, i):
    """Draw one frame of one animation."""
    g = Grid()
    g.rot = params.get("rot", [0] * FRAMES)[i]
    dy = params.get("dy", [0] * FRAMES)[i]
    squash = params.get("squash", [0] * FRAMES)[i]
    arm_l = params.get("arm_l", [0] * FRAMES)[i]
    arm_r = params.get("arm_r", [0] * FRAMES)[i]
    lift_l = params.get("lift_l", [0] * FRAMES)[i]
    lift_r = params.get("lift_r", [0] * FRAMES)[i]
    look = params.get("look", [Z] * FRAMES)[i]
    blink = i in params.get("blink", set())

    X = lambda x: x + W / 2
    Y = lambda y: y + BASE_TOP + dy

    # body: the squash keeps the bottom where it is, so the figure looks landed
    rx = BODY_RX + squash * 1.5
    ry = BODY_RY - squash * 1.5
    body_cy = BODY_CY + (BODY_RY - ry)
    head_cy = HEAD_CY + (BODY_RY - ry) * 0.9
    eye_cy = EYE_CY + (head_cy - HEAD_CY)
    arm_y = body_cy + ARM_DY

    # Layering follows the reference drawing: legs first, then the body (its
    # interior is blanked, hiding the legs inside it), then the head on top
    # (hiding the body's top arc), then the eyes, then the pupils.

    # arms: they leave the body exactly on its edge, which the squash moves
    g.line(X(-rx), Y(arm_y), X(-ARM_X1), Y(arm_y - arm_l))
    g.line(X(rx), Y(arm_y), X(ARM_X1), Y(arm_y - arm_r))

    # legs: a lifted foot also steps a little sideways
    for dx_leg, lift in ((-1, lift_l), (1, lift_r)):
        x_leg = X(dx_leg * LEG_DX) + dx_leg * lift / 3.0
        g.line(X(dx_leg * LEG_DX), Y(arm_y), x_leg, Y(LEG_Y1 - squash - lift))

    g.fill_ellipse(X(0), Y(body_cy), rx + 1, ry + 1, value=False)
    g.ellipse(X(0), Y(body_cy), rx, ry)

    g.fill_ellipse(X(0), Y(head_cy), HEAD_R + 1, HEAD_R + 1, value=False)
    g.ellipse(X(0), Y(head_cy), HEAD_R, HEAD_R)

    for sgn in (-1, 1):
        cx = sgn * EYE_DX
        g.fill_ellipse(X(cx), Y(eye_cy), EYE_R, EYE_R, value=False)
        g.ellipse(X(cx), Y(eye_cy), EYE_R, EYE_R)
        if blink:
            g.line(X(cx - EYE_R + 1), Y(eye_cy), X(cx + EYE_R - 1), Y(eye_cy), thickness=2)
        else:
            g.disc(X(cx + PUPIL_DX + look[0]), Y(eye_cy) + PUPIL_DY + look[1], PUPIL_R)

    # decorations, drawn in canvas coordinates (no lean)
    if params.get("sleep_z"):
        # kept above y ~34 so the z's never sit on the head
        zs = ((40, 12, 2, [0, 3, 5, 6, 5, 3, 0, -3]),
              (28, 22, 1, [0, -2, -4, -5, -4, -2, 0, 2]),
              (52, 18, 1, [0, 2, 4, 5, 4, 2, 0, -2]))
        for zx, zy, sc, seq in zs:
            g.glyph("z", zx, zy - seq[i], scale=sc)
    return g


def pack(g):
    data = bytearray()
    for page in range(H // 8):
        for x in range(W):
            byte = 0
            for bit in range(8):
                if g.px[page * 8 + bit][x]:
                    byte |= 1 << bit
            data.append(byte)
    return bytes(data)


def write_library(path, name, blob, frames_hdr, note):
    with open(path, "w") as fh:
        fh.write("// Generated by make_animations.py - do not edit by hand.\n")
        fh.write("// %s\n" % note)
        fh.write("// %d animations x %d frames of %dx%d px, %d bytes each (%d in total).\n"
                 % (len(blob), FRAMES, W, H, W * H // 8, len(blob) * FRAMES * W * H // 8))
        for n, (aname, desc, _) in enumerate(blob):
            fh.write("//   %d %s - %s\n" % (n, aname, desc))
        fh.write("#pragma once\n\n")
        fh.write("#define %s %d\n" % (frames_hdr[0], FRAMES))
        fh.write("#define %s %d\n\n" % (frames_hdr[1], len(blob)))
        fh.write("static const char PROGMEM %s[%d][%d][%d] = {\n" % (name, len(blob), FRAMES, W * H // 8))
        for aname, desc, frames in blob:
            fh.write("    { // %s\n" % aname)
            for i, data in enumerate(frames):
                fh.write("        { // frame %d\n" % i)
                for k in range(0, len(data), 16):
                    fh.write("            " + ",".join("0x%02x" % b for b in data[k:k + 16]) + ",\n")
                fh.write("        },\n")
            fh.write("    },\n")
        fh.write("};\n")
    print("wrote %s" % path)


def main():
    blob = []
    for name, desc, params in ANIMATIONS:
        frames = [pack(frame(params, i)) for i in range(FRAMES)]
        for i, f in enumerate(frames):
            assert len(f) == W * H // 8, (name, i, len(f))
        blob.append((name, desc, frames))

    # Every pixel flipped: the character comes out dark on a lit panel, which is
    # the daytime counterpart of the default (lit strokes on a dark panel).
    blob_inv = [(name, desc, [bytes(b ^ 0xFF for b in f) for f in frames]) for name, desc, frames in blob]

    write_library(OUT, "oled_anim", blob, ("SOFLE_ANIM_FRAMES", "SOFLE_ANIM_COUNT"),
                  "The animation library, drawn as lit strokes on a dark panel.")
    write_library(OUT_INV, "oled_anim_inv", blob_inv, ("SOFLE_ANIM_INV_FRAMES", "SOFLE_ANIM_INV_COUNT"),
                  "The same library with every pixel flipped (dark character on a lit panel).")

    for label, data in (("normal", blob), ("inverted", blob_inv)):
        print("%s: %d animations x %d frames, %d bytes each, %d bytes total"
              % (label, len(data), FRAMES, W * H // 8, len(data) * FRAMES * W * H // 8))
        for name, _, frames in data:
            print("  %-6s lit pixels per frame: %s" % (name, [sum(bin(b).count("1") for b in f) for f in frames]))


if __name__ == "__main__":
    main()
