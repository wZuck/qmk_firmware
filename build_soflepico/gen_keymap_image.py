#!/usr/bin/env python3
"""从 keymap.c + keyboard.json 生成 sofle_pico 键位图与分层说明。

产物（与本脚本同目录）：
  keymap_layers.png   键位图（默认 2 倍分辨率，可传倍率参数）
  keymap_layers.svg   同一张图的矢量版，放多大都不糊
  keymap.md           分层说明 + 每层键位表

keymap.c 改动后重新跑一次即可刷新：
  python3 gen_keymap_image.py          # PNG 用 2 倍
  python3 gen_keymap_image.py 4        # PNG 用 4 倍

布局以"基础单位"计算，PNG 渲染时整体乘以倍率，SVG 直接输出矢量。
纯标准库 + Pillow。
"""

import html
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KB_JSON = os.path.join(ROOT, "keyboards/sofle_pico/keyboard.json")
KEYMAP_C = os.path.join(ROOT, "keyboards/sofle_pico/keymaps/default/keymap.c")
OUT_PNG = os.path.join(HERE, "keymap_layers.png")
OUT_SVG = os.path.join(HERE, "keymap_layers.svg")
OUT_MD = os.path.join(HERE, "keymap.md")

# PNG 的渲染倍率（布局本身是矢量单位，SVG 不受影响）
SCALE = 2
if len(sys.argv) > 1:
    SCALE = max(1, int(sys.argv[1]))

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"

# --------------------------------------------------------------------------
# 键码 -> 显示名
# --------------------------------------------------------------------------

LABELS = {
    "_______": "▽", "KC_TRNS": "▽", "XXXXXXX": "✗", "KC_NO": "✗",
    "KC_GRV": "`", "KC_1": "1", "KC_2": "2", "KC_3": "3", "KC_4": "4", "KC_5": "5",
    "KC_6": "6", "KC_7": "7", "KC_8": "8", "KC_9": "9", "KC_0": "0",
    "KC_ESC": "Esc", "KC_TAB": "Tab", "KC_BSPC": "Bspc", "KC_ENT": "Enter",
    "KC_SPC": "Space", "KC_LSFT": "Shift", "KC_RSFT": "Shift", "KC_LCTL": "Ctrl",
    "KC_RCTL": "Ctrl", "KC_LALT": "Alt", "KC_RALT": "Alt", "KC_LGUI": "GUI",
    "KC_RGUI": "GUI", "KC_CAPS": "Caps", "KC_INS": "Ins", "KC_DEL": "Del",
    "KC_PSCR": "Pscr", "KC_APP": "Menu", "KC_PGUP": "PgUp", "KC_PGDN": "PgDn",
    "KC_LEFT": "←", "KC_RGHT": "→", "KC_UP": "↑", "KC_DOWN": "↓",
    "KC_MUTE": "Mute", "KC_VOLD": "Vol−", "KC_VOLU": "Vol+",
    "KC_MPLY": "Play", "KC_MPRV": "Prev", "KC_MNXT": "Next",
    "KC_EXLM": "!", "KC_AT": "@", "KC_HASH": "#", "KC_DLR": "$", "KC_PERC": "%",
    "KC_CIRC": "^", "KC_AMPR": "&", "KC_ASTR": "*", "KC_LPRN": "(", "KC_RPRN": ")",
    "KC_PIPE": "|", "KC_EQL": "=", "KC_MINS": "-", "KC_PLUS": "+", "KC_LCBR": "{",
    "KC_RCBR": "}", "KC_LBRC": "[", "KC_RBRC": "]", "KC_SCLN": ";", "KC_COLN": ":",
    "KC_BSLS": "\\", "KC_QUOT": "'", "KC_COMM": ",", "KC_DOT": ".", "KC_SLSH": "/",
    "MO(_LOWER)": "LOWER", "MO(_RAISE)": "RAISE",
    "QK_BOOT": "Boot", "CG_TOGG": "Mac/Win", "EE_CLR": "EE_CLR",
    "OLED_NEXT": "OLED",
    "KC_PRVWD": "词←", "KC_NXTWD": "词→", "KC_LSTRT": "行首", "KC_LEND": "行尾",
    "KC_DLINE": "删行", "KC_UNDO": "Undo", "KC_CUT": "Cut", "KC_COPY": "Copy",
    "KC_PASTE": "Paste",
}
for _i in range(1, 13):
    LABELS[f"KC_F{_i}"] = f"F{_i}"
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    LABELS[f"KC_{_c}"] = _c


def label(code):
    if code in LABELS:
        return LABELS[code]
    if code.startswith("KC_"):
        return code[3:]
    return code


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------


def split_top(body):
    """按顶层逗号切分 C 宏参数，忽略括号内的逗号。"""
    args, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return [a for a in args if a and not a.startswith("//")]


def parse_keymap(src):
    layers = []
    for m in re.finditer(r"\[(_\w+)\]\s*=\s*LAYOUT\s*\(", src):
        i, depth, start = m.end(), 1, m.end()
        while depth:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        layers.append((m.group(1), split_top(src[start : i - 1])))
    return layers


def parse_layout(path):
    data = json.load(open(path))["layouts"]["LAYOUT"]["layout"]
    return [
        {
            "label": k.get("label", ""),
            "matrix": tuple(k["matrix"]),
            "x": k.get("x", 0),
            "y": k.get("y", 0),
            "w": k.get("w", 1),
            "h": k.get("h", 1),
        }
        for k in data
    ]


# --------------------------------------------------------------------------
# 画图
# --------------------------------------------------------------------------

S = 46            # 每个键位单位的像素
GAP = 3
PAD = 22
TITLE_H = 28
NOTE_H = 24
PANEL_GAP = 14

STYLE = {  # 层: (键底色, 键边框, 面板标题色)
    "_QWERTY": ("#ffffff", "#c9ced6", "#37474f"),
    "_LOWER": ("#e8f0fe", "#4a86e8", "#1a56b8"),
    "_RAISE": ("#fdeee0", "#e8811a", "#a85a06"),
    "_ADJUST": ("#f1e8fd", "#8a4fd8", "#6423ad"),
}
NOTE = {
    "_QWERTY": "基础层 0：平时就是这个。按住左拇指 LOWER → 第 1 层；按住右拇指 RAISE → 第 2 层；两个同时按住 → 第 3 层 ADJUST",
    "_LOWER": "第 1 层：按住左手 LOWER 键时生效，松开即回到基础层。拇指区 ▽ 表示该键沿用基础层",
    "_RAISE": "第 2 层：按住右手 RAISE 键时生效。右侧是方向键/翻页/词移动/编辑快捷键，左侧是 Ins/Pscr/Menu/修饰键/撤销复制粘贴",
    "_ADJUST": "第 3 层：LOWER + RAISE 同时按住才进入（三键组合）。放的是 Mac/Win 切换、OLED 画面切换、清 EEPROM、烧录和媒体键",
}


LAYER_INTRO = {
    "_QWERTY": ("基础层（默认）", "开机就是这一层，普通打字用。"),
    "_LOWER": ("数字/符号层", "符号、F1–F12、方向键等；按住左手 LOWER 进入。"),
    "_RAISE": ("导航/编辑层", "方向、翻页、词移动、撤销/复制/粘贴；按住右手 RAISE 进入。"),
    "_ADJUST": ("设置层", "模式切换、OLED 画面切换、清 EEPROM、烧录、媒体键；LOWER+RAISE 同时按住进入。"),
}

ROW_NAMES = ["数字行", "上排", "中排", "下排"]


def load_font(size):
    return ImageFont.truetype(FONT_PATH, int(round(size)))


def fit_size(draw, text, max_w, max_h, hi=16, lo=8):
    """挑一个能塞进格子的字号（基础单位）。"""
    for size in range(hi, lo - 1, -1):
        box = draw.textbbox((0, 0), text, font=load_font(size))
        if box[2] - box[0] <= max_w and box[3] - box[1] <= max_h:
            return size
    return lo


def wrap_text(d, text, font, max_w):
    """按像素宽度折行；尽量在空格处断，中文按字断。"""
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=font) <= max_w:
            cur += ch
            continue
        cut = cur.rfind(" ")
        if cut > 0:
            lines.append(cur[:cut])
            cur = cur[cut + 1 :] + ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------
# 先把整张图摊成图元列表（基础单位），再分别渲染成 PNG 和 SVG。
#   ("rect", x, y, w, h, 圆角, 填充, 描边, 线宽)
#   ("text", x, y, 文本, 字号, 颜色, "lt" 左上 / "ct" 居中)
# --------------------------------------------------------------------------


def build(layout, layers, base_names):
    prims = []
    w_panel = PAD * 2 + 15 * S
    header_h, footer_h = 96, 92
    W = w_panel
    note_font = load_font(14)
    footer_font = load_font(13)
    maxw = w_panel - 2 * PAD

    # 先量文字，再决定每个面板/整图的高度，避免说明被裁掉
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    notes = [wrap_text(probe, NOTE.get(n, ""), note_font, maxw) for n, _ in layers]
    foot1 = wrap_text(probe, "左旋钮：左转 音量−　右转 音量+　按压 静音", footer_font, maxw * 0.48)
    foot2 = wrap_text(probe, "右旋钮：左转 上一首　右转 下一首　按压 播放/暂停", footer_font, maxw * 0.48)
    foot3 = wrap_text(probe, "换层：按住 LOWER（左拇指）/ RAISE（右拇指内侧）；两键同时按 = ADJUST；松开自动回基础层",
                      footer_font, maxw)
    footer_h = 34 + 20 * max(len(foot1), len(foot2)) + 20 * len(foot3) + 12

    heights = [TITLE_H + 6 * S + 20 * len(n) + 14 for n in notes]
    H = header_h + sum(heights) + PANEL_GAP * len(layers) + footer_h

    # 头部
    prims.append(("text", PAD, 20, "Sofle Pico · default keymap 键位图", 26, "#1f2933", "lt"))
    prims.append(("text", PAD, 54,
                  "每个面板：左边 = 左手，右边 = 右手。▽ = 穿透到下一层（用下层的键）　✗ = 无功能",
                  15, "#52606d", "lt"))

    top = header_h
    for idx, (name, args) in enumerate(layers):
        h_panel = heights[idx]
        prims.append(("rect", 6, top, W - 12, h_panel - 4, 10, "#ffffff", "#d7dce3", 1))
        key_fill, key_line, title_color = STYLE.get(name, ("#ffffff", "#c9ced6", "#333333"))
        prims.append(("text", PAD, top + 8, f"第 {idx} 层  {name.lstrip('_')}   ·   {base_names[idx]}",
                      18, title_color, "lt"))

        y_off = top + TITLE_H
        for i, k in enumerate(layout):
            code = args[i] if i < len(args) else "?"
            x0 = PAD + k["x"] * S + GAP / 2
            y0 = y_off + k["y"] * S + GAP / 2
            ww = k["w"] * S - GAP
            hh = k["h"] * S - GAP
            text = label(code)

            if code in ("_______", "KC_TRNS"):
                fill, outline, fg, lw = "#f1f3f5", "#dcdfe4", "#9aa5b1", 1
            elif code in ("XXXXXXX", "KC_NO"):
                fill, outline, fg, lw = "#eceff2", "#e0e3e7", "#b0b8c1", 1
            elif code in ("MO(_LOWER)", "MO(_RAISE)"):
                target = "_LOWER" if "_LOWER" in code else "_RAISE"
                fill, outline, fg, lw = STYLE[target][0], STYLE[target][1], "#202124", 3
            else:
                fill, outline, fg, lw = key_fill, key_line, "#202124", 1

            prims.append(("rect", x0, y0, ww, hh, 6, fill, outline, lw))
            size = fit_size(probe, text, ww - 6, hh - 6)
            prims.append(("text", x0 + ww / 2, y0 + hh / 2, text, size, fg, "ct"))

        ny = y_off + 6 * S + 4
        for line in notes[idx]:
            prims.append(("text", PAD, ny, line, 14, "#52606d", "lt"))
            ny += 20
        top += h_panel + PANEL_GAP

    # 底部图例
    ftop = H - footer_h + 8
    prims.append(("rect", 6, ftop, W - 12, footer_h - 18, 10, "#ffffff", "#d7dce3", 1))
    prims.append(("text", PAD, ftop + 8, "旋钮（左右各一个 EC11）", 16, "#1f2933", "lt"))
    for i, line in enumerate(foot1):
        prims.append(("text", PAD, ftop + 32 + 20 * i, line, 13, "#52606d", "lt"))
    for i, line in enumerate(foot2):
        prims.append(("text", PAD + int(maxw * 0.50), ftop + 32 + 20 * i, line, 13, "#52606d", "lt"))
    y = ftop + 32 + 20 * max(len(foot1), len(foot2)) + 4
    for line in foot3:
        prims.append(("text", PAD, y, line, 13, "#52606d", "lt"))
        y += 20

    return prims, W, H


def emit_png(prims, W, H, path, scale):
    img = Image.new("RGB", (int(round(W * scale)), int(round(H * scale))), "#eef1f5")
    d = ImageDraw.Draw(img)
    for p in prims:
        if p[0] == "rect":
            _, x, y, w, h, r, fill, outline, lw = p
            d.rounded_rectangle([x * scale, y * scale, (x + w) * scale, (y + h) * scale],
                                radius=r * scale, fill=fill, outline=outline, width=max(1, int(round(lw * scale))))
        else:
            _, x, y, s, size, fill, anchor = p
            d.text((x * scale, y * scale), s, font=load_font(size * scale), fill=fill,
                   anchor={"lt": "la", "rt": "ra", "ct": "mm"}.get(anchor, "mm"))
    img.save(path)
    return path


def emit_svg(prims, W, H, path):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="#eef1f5"/>',
           '<style>text{font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",'
           'Helvetica,Arial,sans-serif;}</style>']
    for p in prims:
        if p[0] == "rect":
            _, x, y, w, h, r, fill, outline, lw = p
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
                       f'fill="{fill}" stroke="{outline}" stroke-width="{lw}"/>')
        else:
            _, x, y, s, size, fill, anchor = p
            pos = ("text-anchor=\"middle\" dominant-baseline=\"central\"" if anchor == "ct"
                   else "text-anchor=\"end\" dominant-baseline=\"hanging\"" if anchor == "rt"
                   else "dominant-baseline=\"hanging\"")
            out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" {pos}>'
                       f'{html.escape(s)}</text>')
    out.append("</svg>")
    open(path, "w").write("\n".join(out) + "\n")
    return path


def md_tables(layout, name, args):
    """按物理排列输出两半的键位表。"""
    code_at = {layout[i]["matrix"]: label(a) for i, a in enumerate(args)}
    out = []

    def cell(m):
        return code_at.get(m, "—")

    # 左手：矩阵列 0..5 就是从左到右
    out.append("**左手**\n")
    out.append("| | 1 | 2 | 3 | 4 | 5 | 6 |")
    out.append("|---|---|---|---|---|---|---|")
    for r in range(4):
        out.append(f"| {ROW_NAMES[r]} | " + " | ".join(cell((r, c)) for c in range(6)) + " |")
    out.append("| 拇指/旋钮 | " + " | ".join(cell((4, c)) for c in range(6)) + " |")
    out.append("")
    # 右手：矩阵列 5..0 是从左（内侧）到右（外侧）
    out.append("**右手**\n")
    out.append("| | 1 | 2 | 3 | 4 | 5 | 6 |")
    out.append("|---|---|---|---|---|---|---|")
    for r in range(5, 9):
        out.append(f"| {ROW_NAMES[r - 5]} | " + " | ".join(cell((r, c)) for c in range(5, -1, -1)) + " |")
    out.append("| 拇指/旋钮 | " + " | ".join(cell((9, c)) for c in range(5, -1, -1)) + " |")
    out.append("")
    return "\n".join(out)


def write_md(layout, layers):
    names = [n.lstrip("_") for n, _ in layers]
    parts = []
    parts.append("# sofle_pico `default` 键位图与分层说明\n")
    parts.append("![四层键位图](keymap_layers.png)\n")
    parts.append("> 放大看不糊的矢量版：[keymap_layers.svg](keymap_layers.svg)\n")
    parts.append("> 图片由 `gen_keymap_image.py` 从 `keymap.c` + `keyboard.json` 自动生成，"
                 "改键后重跑该脚本即可刷新。\n")

    parts.append("## 一、层的切换方式\n")
    parts.append("固件一共 4 层，**只有两个键负责换层，全部在拇指区**：\n")
    parts.append("| 层号 | 层名 | 怎么进入 | 松开后 |")
    parts.append("|---|---|---|---|")
    parts.append("| 0 | QWERTY | 默认基础层（开机即此层） | — |")
    parts.append("| 1 | LOWER | **按住**左手拇指的 `LOWER` 键 | 松开回到基础层 |")
    parts.append("| 2 | RAISE | **按住**右手拇指的 `RAISE` 键 | 松开回到基础层 |")
    parts.append("| 3 | ADJUST | **同时按住** `LOWER` + `RAISE` | 松开任意一个即退出 |")
    parts.append("")
    parts.append("拇指区的两个换层键位置（看图更直观）：\n")
    parts.append("```")
    parts.append("      左手拇指区                     右手拇指区")
    parts.append("  GUI  Alt  Ctrl  [LOWER]  Enter | Space  [RAISE]  Ctrl  Alt  GUI")
    parts.append("                     ↑                        ↑")
    parts.append("              按住 = 第1层              按住 = 第2层")
    parts.append("              两个一起按住 = 第3层 ADJUST（三键组合，不会误触）")
    parts.append("```\n")
    parts.append("其它切换类按键（都在 ADJUST 层）：\n")
    parts.append("- `OLED`（`OLED_NEXT`，左右各一个）：切换**本侧** OLED 的画面（status / anim / logo）。")
    parts.append("- `EE_CLR`：清空 EEPROM。因为 VIA 把键位存在 EEPROM 里，改了 keymap 之后需要清一次才会生效。")
    parts.append("- `Mac/Win`（`CG_TOGG`）：切换 Mac 与 Win/Linux 模式，"
                 "影响修饰键顺序以及 RAISE 层的行首/行尾/词移动等快捷键，选择同样存 EEPROM。")
    parts.append("- `Boot`（`QK_BOOT`）：进入 bootloader 准备烧录；按住 Pico 的 BOOT 键插 USB 也可以。\n")

    parts.append("## 二、每层的键位\n")
    parts.append("每层给两张表：**左手**从最左列到最右列；**右手**按从内到外（靠近中间缝 → 最外侧）排列。"
                 "手指的实际位置看上面的图更直观。\n")
    for idx, (name, args) in enumerate(layers):
        title, desc = LAYER_INTRO.get(name, ("", ""))
        parts.append(f"### 第 {idx} 层 · {name.lstrip('_')} — {title}\n")
        parts.append(desc + "\n")
        parts.append(md_tables(layout, name, args))
    parts.append("表内符号：`▽` = 穿透（沿用下一层的键），`✗` = 无功能。\n")

    parts.append("## 三、旋钮\n")
    parts.append("| 旋钮 | 左转（逆时针） | 右转（顺时针） | 按压 |")
    parts.append("|---|---|---|---|")
    parts.append("| 左手 EC11 | 音量 − | 音量 + | 静音 `Mute` |")
    parts.append("| 右手 EC11 | 上一首 `Prev` | 下一首 `Next` | 播放/暂停 `Play` |")
    parts.append("")
    parts.append("两个旋钮在所有层都可用（上层用 `▽` 穿透到基础层的定义）。\n")

    parts.append("## 四、自定义键说明\n")
    parts.append("| 键位显示 | 键码 | 作用 |")
    parts.append("|---|---|---|")
    parts.append("| `LOWER` / `RAISE` | `MO(_LOWER)` / `MO(_RAISE)` | 按住临时切层 |")
    parts.append("| `OLED` | `OLED_NEXT` | 切换本侧 OLED 的画面（status → anim → logo → status） |")
    parts.append("| `EE_CLR` | `EE_CLR` | 清空 EEPROM（VIA 键位存 EEPROM，改键后需要清） |")
    parts.append("| `Mac/Win` | `CG_TOGG` | 切换 Mac / Win 模式 |")
    parts.append("| `词←` / `词→` | `KC_PRVWD` / `KC_NXTWD` | 按模式发送 Ctrl+←/→ 或 Alt+←/→（按词移动） |")
    parts.append("| `行首` / `行尾` | `KC_LSTRT` / `KC_LEND` | Home/End；Mac 模式下发 Cmd+←/→ |")
    parts.append("| `删行` | `KC_DLINE` | Ctrl+Backspace（删到行首） |")
    parts.append("| `Undo` `Cut` `Copy` `Paste` | `KC_UNDO` … | 按模式发送 Ctrl 或 Cmd 组合键 |")
    parts.append("| `Boot` | `QK_BOOT` | 进入 bootloader |")
    parts.append("")

    open(OUT_MD, "w").write("\n".join(parts))
    return OUT_MD


def main():
    layout = parse_layout(KB_JSON)
    src = open(KEYMAP_C).read()
    layers = parse_keymap(src)
    if not layers:
        sys.exit("没有从 keymap.c 解析到任何层")
    for name, args in layers:
        if len(args) != len(layout):
            sys.exit(f"{name}: 参数 {len(args)} 个，layout 有 {len(layout)} 个")

    unknown = sorted({a for _, args in layers for a in args
                      if a not in LABELS and not a.startswith("KC_")})
    base_names = ["基础层 · QWERTY", "符号层", "导航/编辑层", "设置层"]
    prims, W, H = build(layout, layers, base_names[: len(layers)])
    png = emit_png(prims, W, H, OUT_PNG, SCALE)
    svg = emit_svg(prims, W, H, OUT_SVG)
    md = write_md(layout, layers)
    print("层:", ", ".join(n for n, _ in layers))
    print("键位数/层:", len(layout))
    if unknown:
        print("未映射的键码（用了 fallback 显示）:", unknown)
    print(f"已生成: {png}  ({int(round(W * SCALE))}x{int(round(H * SCALE))}, {SCALE} 倍)")
    print(f"已生成: {svg}  (矢量, {W}x{H} 单位)")
    print("已生成:", md)


if __name__ == "__main__":
    main()
