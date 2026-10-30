#!/usr/bin/env python3
"""Generate deterministic 64 x 128 OLED game illustrations.

The three source canvases mirror the layouts in keymaps/default/game.c:
Tetris and Snake information on the left, with text-free bordered game screens
on the right. The composite image is used by both the firmware README and the
build_soflepico web page.
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "game_preview.png"
ONE_X = HERE / "1x"
FOUR_X = HERE / "4x"

WIDTH, HEIGHT = 64, 128

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"

FONT_5X7 = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11100", "10010", "10001", "10001", "10001", "10010", "11100"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
}


class Canvas:
    def __init__(self):
        self.pixels = bytearray(WIDTH * HEIGHT)

    def pixel(self, x, y, value=1):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.pixels[y * WIDTH + x] = value

    def rect(self, x, y, width, height, value=1):
        for yy in range(y, y + height):
            for xx in range(x, x + width):
                self.pixel(xx, yy, value)

    def outline(self, x, y, width, height):
        self.rect(x, y, width, 1)
        self.rect(x, y + height - 1, width, 1)
        self.rect(x, y, 1, height)
        self.rect(x + width - 1, y, 1, height)

    def text(self, x, y, text, scale=1, value=1):
        for char in text:
            glyph = FONT_5X7.get(char)
            if glyph:
                for row, bits in enumerate(glyph):
                    for col, bit in enumerate(bits):
                        if bit == "1":
                            self.rect(x + col * scale, y + row * scale, scale, scale, value)
            x += 6 * scale

    def number(self, x, y, value, scale=1):
        self.text(x, y, str(value), scale)

    def image(self, scale):
        image = Image.new("RGB", (WIDTH, HEIGHT), "#0a0e12")
        image.putdata([(245, 249, 252) if p else (10, 14, 18) for p in self.pixels])
        if scale != 1:
            image = image.resize((WIDTH * scale, HEIGHT * scale), Image.Resampling.NEAREST)
        return image


def draw_tetris_piece(canvas, x, y, mask, cell_width, cell_height):
    for row in range(4):
        for col in range(4):
            if mask & (0x8000 >> (row * 4 + col)):
                canvas.rect(x + col * cell_width, y + row * cell_height, cell_width - 1, cell_height - 1)


def game_menu():
    canvas = Canvas()
    canvas.outline(0, 0, WIDTH, HEIGHT)
    canvas.text(4, 8, "GAME", 2)
    canvas.rect(4, 30, 56, 1)
    canvas.rect(3, 44, 58, 12)
    canvas.text(6, 46, "SNAKE", 1, 0)
    canvas.text(6, 66, "TETRIS", 1)
    canvas.text(6, 104, "ENTER", 1)
    return canvas


def tetris_sidebar():
    canvas = Canvas()
    canvas.outline(0, 0, WIDTH, HEIGHT)
    canvas.text(4, 4, "NEXT")
    draw_tetris_piece(canvas, 12, 18, 0x7200, 8, 8)
    canvas.text(4, 62, "SCORE")
    canvas.number(4, 72, 2480, 2)
    canvas.text(4, 92, "LEVEL")
    canvas.number(50, 92, 3)
    canvas.text(4, 104, "LINES")
    canvas.number(50, 104, 24)
    return canvas


def tetris_board():
    canvas = Canvas()
    canvas.outline(0, 0, WIDTH, HEIGHT)
    ox, oy = 2, 4
    cw = ch = 6
    cells = {(x, y) for y in range(14, 20) for x in range(10) if (x + y) % 3 != 0}
    cells |= {(4, 3), (5, 3), (6, 3), (5, 4)}
    for x, y in cells:
        canvas.rect(ox + x * cw, oy + y * ch, cw - 1, ch - 1)
    return canvas


def snake_info():
    canvas = Canvas()
    canvas.outline(0, 0, WIDTH, HEIGHT)
    canvas.text(2, 8, "SNAKE", 2)
    canvas.text(4, 38, "SCORE")
    canvas.number(4, 48, 120, 2)
    canvas.text(4, 76, "LENGTH")
    canvas.number(4, 86, 10)
    canvas.text(4, 108, "STATUS")
    canvas.text(4, 118, "RUNNING")
    return canvas


def snake_screen():
    canvas = Canvas()
    canvas.outline(0, 0, WIDTH, HEIGHT)
    cell, top = 4, 2
    body = [(6, 14), (7, 14), (8, 14), (9, 14), (9, 13), (9, 12), (10, 12)]
    for x, y in body:
        canvas.rect(x * cell, top + y * cell, cell, cell)
    hx, hy = body[-1]
    canvas.rect(hx * cell + 1, top + hy * cell + 1, 2, 2, 0)
    canvas.rect(13 * cell + 1, top + 7 * cell + 1, 2, 2)
    return canvas


def load_font(size, bold=False):
    path = FONT_PATH
    if not os.path.exists(path):
        path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"
    return ImageFont.truetype(path, size)


def main():
    ONE_X.mkdir(exist_ok=True)
    FOUR_X.mkdir(exist_ok=True)

    canvases = {
        "game_menu": game_menu(),
        "game_tetris_left": tetris_sidebar(),
        "game_tetris_right": tetris_board(),
        "game_snake_left": snake_info(),
        "game_snake_right": snake_screen(),
    }
    for name, canvas in canvases.items():
        canvas.image(1).save(ONE_X / f"{name}.png")
        canvas.image(4).save(FOUR_X / f"{name}.png")

    scale = 4
    screen_w, screen_h = WIDTH * scale, HEIGHT * scale
    margin = 42
    gap = 30
    canvas_w = margin * 2 + screen_w * 5 + gap * 4
    canvas_h = 790
    image = Image.new("RGB", (canvas_w, canvas_h), "#eef1f5")
    draw = ImageDraw.Draw(image)

    draw.text((margin, 24), "Sofle Pico · OLED 游戏界面", fill="#1f2933", font=load_font(34, True))
    draw.text((margin, 70), "游戏层使用完整 64×128 竖屏；右手只画游戏，所有文字都在左手。",
              fill="#52606d", font=load_font(19))

    labels = [
        ("game_menu", "GAME · 方向键高亮 / Enter 确认"),
        ("game_tetris_left", "TETRIS · 左手：全部文字"),
        ("game_tetris_right", "TETRIS · 右手：仅正方形棋盘"),
        ("game_snake_left", "SNAKE · 左手：全部文字"),
        ("game_snake_right", "SNAKE · 右手：仅游戏画面"),
    ]
    top = 142
    for index, (name, label) in enumerate(labels):
        x = margin + index * (screen_w + gap)
        draw.text((x, top - 34), label, fill="#17663e", font=load_font(18, True))
        image.paste(canvases[name].image(scale), (x, top))

    draw.text((margin, 708), "右屏所有游戏画面最外层都有 1 像素边框；俄罗斯方块每个单元格固定为 6×6 像素。",
              fill="#52606d", font=load_font(18))
    draw.text((margin, canvas_h - 34), "示意图按 game.c 的 64×128 竖屏布局生成；实际屏幕为单色 OLED。",
              fill="#77818c", font=load_font(16))
    image.save(OUT)
    print("generated:", OUT)


if __name__ == "__main__":
    main()
