#!/usr/bin/env python3
"""画左半的矩阵排查图：每个键标出物理键位 + 矩阵坐标，按实测状态着色。

状态来自左手实机跑 probe 固件的结果：
  绿 = 实测能出字符，红 = 实测不出，灰 = 还没测过
边框颜色 = 该键所在列（用来一眼看出"整列不通"）。

用法： python3 gen_matrix_image.py [放大倍数]
输出： matrix_map_left.png / matrix_map_left.svg
"""

import os
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gen_keymap_image import emit_png, emit_svg, load_font, parse_layout  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

SCALE = int(sys.argv[1]) if len(sys.argv) > 1 else 2

COL_PINS = ["GP1", "GP2", "GP3", "GP4", "GP5", "GP8"]
ROW_PINS = ["GP9", "GP10", "GP11", "GP12", "GP13"]
COL_COLOR = ["#c0392b", "#d68910", "#b7950b", "#1e8449", "#2471a3", "#7d3c98"]

# 实机结果（probe 固件）
WORKS = {(0, 4), (0, 5), (1, 4), (1, 5), (2, 4), (2, 5), (3, 4), (3, 5), (4, 3), (4, 4)}
DEAD = {(r, c) for r in range(4) for c in range(4)}
UNKNOWN = {(4, 0), (4, 1), (4, 2), (4, 5)}

KEYNAME = {
    (0, 0): "`", (0, 1): "1", (0, 2): "2", (0, 3): "3", (0, 4): "4", (0, 5): "5",
    (1, 0): "Esc", (1, 1): "Q", (1, 2): "W", (1, 3): "E", (1, 4): "R", (1, 5): "T",
    (2, 0): "Tab", (2, 1): "A", (2, 2): "S", (2, 3): "D", (2, 4): "F", (2, 5): "G",
    (3, 0): "Shift", (3, 1): "Z", (3, 2): "X", (3, 3): "C", (3, 4): "V", (3, 5): "B",
    (4, 0): "GUI", (4, 1): "Alt", (4, 2): "Ctrl", (4, 3): "LOWER", (4, 4): "Enter", (4, 5): "旋钮按",
}

S = 62
GAP = 4
PAD = 28
TOP = 84        # 标题区高度
LEGEND_GAP = 20

LEGEND = [
    ("引脚对照（COL2ROW：列是带上拉的输入，行是输出）", 19, "#1f2933"),
    ("行：" + "   ".join(f"r{i}={p}" for i, p in enumerate(ROW_PINS)), 16, "#52606d"),
    ("列：" + "   ".join(f"c{i}={p}" for i, p in enumerate(COL_PINS)), 16, "#52606d"),
    ("", 10, "#000000"),
    ("实测结论：列 0-3（GP1/GP2/GP3/GP4）在行 0-3 整片不出；列 4-5（GP5/GP8）正常。", 16, "#8c1c1c"),
    ("但拇指行的 c3（GP4，LOWER）是好的 → 断点在「拇指行以上」的列线，或 Pico 引脚本身。", 16, "#8c1c1c"),
    ("", 10, "#000000"),
    ("排查顺序：", 16, "#1f2933"),
    ("1. 烧 sofle_pico_pintest.uf2，把 Pico 拔下来单独插 USB 跑，看 col0-col3 的 up/down/low", 15, "#52606d"),
    ("2. 烧 sofle_pico_debug.uf2，跳线短接引脚根部（不是焊盘）与 GP9，看 console 出不出 DOWN r0 cX", 15, "#52606d"),
    ("3. 万用表：断电量 GP1↔GND / GP1↔3V3 是否短路；通电量各列脚空载电压是否都在 3.3V 附近", 15, "#52606d"),
]


def text_w(text, size):
    if not text:
        return 0
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    return probe.textlength(text, font=load_font(size))


def build():
    layout = [k for k in parse_layout(os.path.join(HERE, "..", "keyboards", "sofle_pico", "keyboard.json"))
              if k["matrix"][0] < 5]

    minx = min(k["x"] for k in layout)
    grid_right = PAD + (max(k["x"] + k["w"] for k in layout) - minx) * S
    grid_bottom = TOP + max(k["y"] + k["h"] for k in layout) * S

    legend_top = grid_bottom + LEGEND_GAP
    legend_h = 24 + sum(24 if size >= 16 else 20 for _, size, _ in LEGEND)
    W = int(max(grid_right + PAD, max(text_w(t, s) for t, s, _ in LEGEND) + PAD * 2 + 16))
    H = int(legend_top + legend_h + PAD)

    prims = [
        ("text", PAD, 16, "左手矩阵排查图 · sofle_pico", 30, "#1f2933", "lt"),
        ("text", PAD, 56, "绿 = 实测出字符　红 = 实测不出　灰 = 未测　　边框颜色 = 所属列", 16, "#52606d", "lt"),
    ]

    for k in layout:
        r, c = k["matrix"]
        x0 = PAD + (k["x"] - minx) * S + GAP / 2
        y0 = TOP + k["y"] * S + GAP / 2
        ww = k["w"] * S - GAP
        hh = k["h"] * S - GAP

        if (r, c) in DEAD:
            fill, fg = "#fbd5d5", "#8c1c1c"
        elif (r, c) in WORKS:
            fill, fg = "#d6f0dc", "#1b5e20"
        else:
            fill, fg = "#eef1f5", "#7b8794"

        prims.append(("rect", x0, y0, ww, hh, 8, fill, COL_COLOR[c], 4))
        name = KEYNAME.get((r, c), "")
        size = 24 if text_w(name, 24) < ww - 8 else 15
        prims.append(("text", x0 + ww / 2, y0 + hh * 0.33, name, size, fg, "ct"))
        prims.append(("text", x0 + ww / 2, y0 + hh * 0.70, f"r{r}c{c}", 15, "#52606d", "ct"))

    y = legend_top
    prims.append(("rect", 10, y - 8, W - 20, legend_h, 12, "#ffffff", "#d7dce3", 1))
    y += 14
    for text, size, color in LEGEND:
        if text:
            prims.append(("text", PAD, y, text, size, color, "lt"))
        y += 24 if size >= 16 else 20

    return prims, W, H


def main():
    prims, W, H = build()
    png = emit_png(prims, W, H, os.path.join(HERE, "matrix_map_left.png"), SCALE)
    svg = emit_svg(prims, W, H, os.path.join(HERE, "matrix_map_left.svg"))
    print("已生成:", png, svg)


if __name__ == "__main__":
    main()
