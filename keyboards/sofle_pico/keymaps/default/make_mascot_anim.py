#!/usr/bin/env python3
"""Generate oled_anim.h - the mascot animation for the right half.

The character is the little big-eyed blob from the reference drawing: a round
head with two large overlapping eyes, an oval body, straight arms out to the
sides and two legs.

Proportions are taken from the reference bitmap (114 x 120 px of ink) and
scaled to fit the 64 px wide canvas: arms tip to tip span the whole width, so
the figure ends up 67 px tall - which leaves the tall 64 x 128 canvas room for
an 8 frame bouncing loop.

Everything is drawn from primitives (line / ellipse / disc) into a 1 bit grid,
then packed into the SSD1306 page format the driver expects. Pure stdlib.

Run from anywhere; it writes oled_anim.h next to itself.
"""

import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "oled_anim.h")

W, H = 64, 128
FRAMES = 8
STROKE = 2          # line width, in pixels

# ---------------------------------------------------------------------------
# Figure geometry, in "figure" coordinates: origin at the body centre line,
# y grows downwards, y = 0 is the head's centre. Measured off the reference
# bitmap (ink box 114 x 120 px) and scaled by 64/114, so the arms span the full
# 64 px canvas and the figure stands 66 px tall - which leaves the tall
# 64 x 128 canvas room for the bounce.
# ---------------------------------------------------------------------------

HEAD_CY, HEAD_R = 12.0, 9.5
EYE_DX, EYE_CY, EYE_R = 5.0, 9.0, 6.0
PUPIL_R, PUPIL_DX = 2.5, 2.0
BODY_CY, BODY_RX, BODY_RY = 34.5, 17.0, 23.5
ARM_Y, ARM_X1 = 34.5, 31.5
LEG_DX, LEG_Y1 = 13.5, 67.5

BASE_TOP = 32       # where the figure's y=0 lands at the bottom of the bounce

# One bounce per loop: up on frames 1-5, down on 6-7, so it repeats seamlessly.
BOUNCE = [0, -3, -9, -14, -16, -14, -9, -3]
SQUASH = [1.0, 0.5, -0.3, -1.0, -1.0, -0.3, 0.5, 1.0]     # +1 landed, -1 stretched
ARM_WAVE = [0, 3, 5, 3, 0, -3, -5, -3]
LOOK = [(0, 0), (1, 0), (2, 0), (2, -1), (2, 0), (1, 0), (0, 0), (-1, 0)]
BLINK = {4, 5}      # frames with the eyes shut


class Grid:
    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.px = [[False] * w for _ in range(h)]

    def plot(self, x, y, thickness=STROKE, value=True):
        for dy in range(thickness):
            for dx in range(thickness):
                xi, yi = int(round(x)) + dx, int(round(y)) + dy
                if 0 <= xi < self.w and 0 <= yi < self.h:
                    self.px[yi][xi] = value

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
        n = int(360 / step_deg)
        for i in range(n):
            t = math.radians(i * step_deg)
            self.plot(cx + rx * math.cos(t), cy + ry * math.sin(t), thickness, value)

    def fill_ellipse(self, cx, cy, rx, ry, value=False):
        """Solid ellipse (used with value=False to blank a shape's interior)."""
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    if 0 <= x < self.w and 0 <= y < self.h:
                        self.px[y][x] = value

    def disc(self, cx, cy, r, value=True):
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    if 0 <= x < self.w and 0 <= y < self.h:
                        self.px[y][x] = value


def figure(frame):
    g = Grid()
    dy = BOUNCE[frame]
    sq = SQUASH[frame]
    wave = ARM_WAVE[frame]
    look = LOOK[frame]
    blink = frame in BLINK

    def X(x):
        return x + W / 2

    def Y(y):
        return y + BASE_TOP + dy

    # body: squash keeps the bottom where it is, so the figure looks like it lands
    rx = BODY_RX + sq * 1.5
    ry = BODY_RY - sq * 1.5
    body_cy = BODY_CY + (BODY_RY - ry)

    # head drops with the squash as well
    head_cy = HEAD_CY + (BODY_RY - ry) * 0.9
    eye_cy = EYE_CY + (head_cy - HEAD_CY)

    # Layering follows the reference drawing: legs first, then the body (its
    # interior is blanked, which hides the legs inside it), then the head on
    # top (which hides the body's top arc), then the eyes (which hide the head
    # outline behind them), then the pupils.

    # arms swing around the shoulder, one up while the other is down; they
    # start exactly on the body's edge, which the squash moves in and out
    arm_y = ARM_Y + (BODY_RY - ry)
    g.line(X(-rx), Y(arm_y), X(-ARM_X1), Y(arm_y - wave))
    g.line(X(rx), Y(arm_y), X(ARM_X1), Y(arm_y + wave))

    for sgn in (-1, 1):
        foot_y = Y(LEG_Y1 - sq)
        g.line(X(sgn * LEG_DX), Y(arm_y), X(sgn * LEG_DX), foot_y)

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
            g.disc(X(cx + PUPIL_DX + look[0]), Y(eye_cy) + look[1], PUPIL_R)
    return g


def pack(grid):
    data = bytearray()
    for page in range(H // 8):
        for x in range(W):
            byte = 0
            for bit in range(8):
                if grid.px[page * 8 + bit][x]:
                    byte |= 1 << bit
            data.append(byte)
    return bytes(data)


def main():
    frames = [pack(figure(i)) for i in range(FRAMES)]
    for i, f in enumerate(frames):
        assert len(f) == W * H // 8, (i, len(f))

    with open(OUT, "w") as fh:
        fh.write("// Generated by make_mascot_anim.py - do not edit by hand.\n")
        fh.write("// %d frames of %dx%d px, %d bytes each (%d in total).\n"
                 % (FRAMES, W, H, len(frames[0]), FRAMES * len(frames[0])))
        fh.write("// Character: big-eyed blob - bounces, blinks, waves its arms.\n")
        fh.write("#pragma once\n\n")
        fh.write("#define SOFLE_ANIM_FRAMES %d\n\n" % FRAMES)
        fh.write("static const char PROGMEM oled_anim[SOFLE_ANIM_FRAMES][%d] = {\n" % len(frames[0]))
        for i, data in enumerate(frames):
            fh.write("    { // frame %d\n" % i)
            for k in range(0, len(data), 16):
                fh.write("        " + ",".join("0x%02x" % b for b in data[k:k + 16]) + ",\n")
            fh.write("    },\n")
        fh.write("};\n")

    lit = [sum(bin(b).count("1") for b in f) for f in frames]
    print("wrote %s" % OUT)
    print("%d frames, %d bytes each, %d bytes total" % (FRAMES, len(frames[0]), FRAMES * len(frames[0])))
    print("lit pixels per frame: %s" % lit)


if __name__ == "__main__":
    main()
