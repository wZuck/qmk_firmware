#!/usr/bin/env python3
"""Validate the firmware's 4x4 Tetris rotation masks.

Every rotation must contain four connected cells, and each next rotation must
be the same shape rotated by 90 degrees (translation is allowed).
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "keyboards/sofle_pico/keymaps/default/game.c"


def cells(mask):
    return {(x, y) for y in range(4) for x in range(4) if mask & (0x8000 >> (y * 4 + x))}


def normalized(shape):
    min_x = min(x for x, _ in shape)
    min_y = min(y for _, y in shape)
    return {(x - min_x, y - min_y) for x, y in shape}


def rotated(shape):
    return {(3 - y, x) for x, y in shape}


def main():
    source = SOURCE.read_text(encoding="utf-8")
    body = re.search(r"static const uint16_t tetrominoes\[7\]\[4\] = \{(.*?)\n\};", source, re.S).group(1)
    rotations = []
    for line in body.splitlines():
        values = re.findall(r"0x[0-9A-Fa-f]+", line)
        if values:
            rotations.append([int(value, 16) for value in values])

    assert len(rotations) == 7, f"expected 7 pieces, got {len(rotations)}"
    for piece, masks in zip("IOTSZJL", rotations):
        assert len(masks) == 4, f"{piece}: expected 4 rotations"
        for index, mask in enumerate(masks):
            shape = cells(mask)
            assert len(shape) == 4, f"{piece}[{index}]: expected 4 cells"

            connected = {next(iter(shape))}
            while True:
                expanded = connected | {
                    (x + dx, y + dy)
                    for x, y in connected
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if (x + dx, y + dy) in shape
                }
                if expanded == connected:
                    break
                connected = expanded
            assert connected == shape, f"{piece}[{index}]: disconnected cells"

            next_shape = cells(masks[(index + 1) % 4])
            assert normalized(rotated(shape)) == normalized(next_shape), f"{piece}[{index}]: not a 90-degree rotation"

    print("OK: 7 pieces x 4 rotations are connected and rotate by a true 90 degrees")


if __name__ == "__main__":
    main()
