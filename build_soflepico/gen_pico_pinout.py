#!/usr/bin/env python3
"""画 RP2040 Pico 的引脚图，标出 sofle_pico 用到哪些脚、各自是什么功能。

用法： python3 gen_pico_pinout.py [放大倍数]
输出： pico_pinout.png / pico_pinout.svg
"""

import os
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gen_keymap_image import emit_png, emit_svg, load_font  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

SCALE = int(sys.argv[1]) if len(sys.argv) > 1 else 2

COL = "#2471a3"
ROW = "#1e8449"
RGB = "#d68910"
OLED = "#7d3c98"
ENC = "#00838f"
SER = "#c0392b"
OFF = "#b0b8c1"

# (物理脚号, 名称, 功能, 颜色)
LEFT = [
    (1, "GP0", "RGB 灯带数据", RGB), (2, "GP1", "矩阵列 c0", COL), (3, "GND", "", OFF),
    (4, "GP2", "矩阵列 c1", COL), (5, "GP3", "矩阵列 c2", COL), (6, "GP4", "矩阵列 c3", COL),
    (7, "GP5", "矩阵列 c4", COL), (8, "GND", "", OFF), (9, "GP6", "OLED SDA", OLED),
    (10, "GP7", "OLED SCL", OLED), (11, "GP8", "矩阵列 c5", COL), (12, "GP9", "矩阵行 r0", ROW),
    (13, "GND", "", OFF), (14, "GP10", "矩阵行 r1", ROW), (15, "GP11", "矩阵行 r2", ROW),
    (16, "GP12", "矩阵行 r3", ROW), (17, "GP13", "矩阵行 r4", ROW), (18, "GND", "", OFF),
    (19, "GP14", "旋钮 A", ENC), (20, "GP15", "旋钮 B", ENC),
]
RIGHT = [  # 从下往上（21 在底部）
    (40, "VBUS", "", OFF), (39, "VSYS", "", OFF), (38, "GND", "", OFF), (37, "3V3_EN", "", OFF),
    (36, "3V3(OUT)", "", OFF), (35, "ADC_VREF", "", OFF), (34, "GP28", "", OFF),
    (33, "AGND", "", OFF), (32, "GP27", "", OFF), (31, "GP26", "", OFF), (30, "RUN", "", OFF),
    (29, "GP22", "", OFF), (28, "GND", "", OFF), (27, "GP21", "", OFF), (26, "GP20", "", OFF),
    (25, "GP19", "", OFF), (24, "GP18", "", OFF), (23, "GND", "", OFF),
    (22, "GP17", "TRRS RX（连另一半）", SER), (21, "GP16", "TRRS TX（连另一半）", SER),
]

PITCH = 36
BOARD_W = 132
PIN_W = 16
BOARD_TOP = 110
LABEL_GAP = 14
PAD = 30


def text_w(text, size):
    if not text:
        return 0
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    return probe.textlength(text, font=load_font(size))


def build():
    board_h = PITCH * 20 + 20
    board_x = 330
    # 左右两侧文字所需宽度
    left_w = max(text_w(f"GP13  17 矩阵行 r4", 16) for _, _, _, _ in LEFT) + 20
    right_w = max(text_w(f"GP16  21 TRRS TX（连另一半）", 16) for _, _, _, _ in RIGHT) + 20
    W = int(board_x + BOARD_W + LABEL_GAP + right_w + PAD)
    H = int(BOARD_TOP + board_h + 250)

    prims = [
        ("text", PAD, 16, "RP2040 Pico 引脚对照 · sofle_pico 用到的脚", 30, "#1f2933", "lt"),
        ("text", PAD, 56, "两个半边各一块 Pico，接线方式相同；未列出的脚空着不用", 16, "#52606d", "lt"),
    ]

    # 板子本体
    prims.append(("rect", board_x, BOARD_TOP, BOARD_W, board_h, 14, "#e8f2e8", "#2e7d32", 2))
    prims.append(("text", board_x + BOARD_W / 2, BOARD_TOP + 26, "RP2040", 20, "#2e7d32", "ct"))
    prims.append(("text", board_x + BOARD_W / 2, BOARD_TOP + 52, "Pico", 20, "#2e7d32", "ct"))
    prims.append(("rect", board_x + BOARD_W * 0.30, BOARD_TOP - 14, BOARD_W * 0.40, 14, 3, "#c8d6c8", "#7ba17b", 1))
    prims.append(("text", board_x + BOARD_W / 2, BOARD_TOP - 7, "USB", 10, "#3d5a3d", "ct"))

    def draw_side(items, top_to_bottom, side):
        for i, (num, name, func, color) in enumerate(items):
            idx = i if top_to_bottom else len(items) - 1 - i
            y = BOARD_TOP + 16 + idx * PITCH
            if side == "left":
                prims.append(("rect", board_x - PIN_W / 2, y - 5, PIN_W, 10, 2, color, color, 0))
                tx = board_x - PIN_W / 2 - 10
                anchor = "rt"
            else:
                prims.append(("rect", board_x + BOARD_W - PIN_W / 2, y - 5, PIN_W, 10, 2, color, color, 0))
                tx = board_x + BOARD_W + PIN_W / 2 + 10
                anchor = "lt"
            label = f"{name}"
            prims.append(("text", tx, y - 9, label, 17, color if func else "#6b7684", anchor))
            sub = f"pin {num}" + (f" · {func}" if func else "")
            prims.append(("text", tx, y + 8, sub, 13, color if func else OFF, anchor))

    draw_side(LEFT, True, "left")
    draw_side(RIGHT, True, "right")

    # 图例
    y = BOARD_TOP + board_h + 24
    prims.append(("text", PAD, y, "图例", 20, "#1f2933", "lt"))
    y += 30
    for color, text in [(COL, "矩阵列 c0-c5：GP1 GP2 GP3 GP4 GP5 GP8（带上拉的输入，最常见故障点）"),
                        (ROW, "矩阵行 r0-r4：GP9 GP10 GP11 GP12 GP13（扫描时逐个拉低）"),
                        (SER, "分体链路：GP16/GP17，走 TRRS 线到另一半"),
                        (ENC, "旋钮：GP14/GP15"), (OLED, "OLED I2C：GP6= SDA、GP7=SCL"),
                        (RGB, "RGB 灯带数据：GP0")]:
        prims.append(("rect", PAD, y + 4, 14, 14, 3, color, color, 0))
        prims.append(("text", PAD + 24, y, text, 16, "#52606d", "lt"))
        y += 26
    y += 6
    prims.append(("text", PAD, y, "测列线：把 Pico 拔下单插 USB 跑 sofle_pico_pintest.uf2，或用跳线把引脚根部短接到 GP9 看 debug 输出。",
                  15, "#8c1c1c", "lt"))

    return prims, W, H


def main():
    prims, W, H = build()
    png = emit_png(prims, W, H, os.path.join(HERE, "pico_pinout.png"), SCALE)
    svg = emit_svg(prims, W, H, os.path.join(HERE, "pico_pinout.svg"))
    print("已生成:", png, svg)


if __name__ == "__main__":
    main()
