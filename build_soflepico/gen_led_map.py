#!/usr/bin/env python3
"""画 sofle_pico 的 LED（逐键 RGB）分布图。

数据来源：keyboards/sofle_pico/keyboard.json 的 rgb_matrix.layout（数组顺序 = LED 索引，
坐标 = 固件算灯效用的位置），并与已编译固件的产物
.build/obj_sofle_pico_default/src/default_keyboard.c 里的 g_led_config 逐项核对。
（default 就是 split-left / split-right 那两个 uf2 的来源，所以图上就是烧进去的样子。）

产物（与本脚本同目录）：
  led_map.png   位图（默认 2 倍）
  led_map.svg   矢量版

用法： python3 gen_led_map.py [放大倍数]
"""

import colorsys
import html
import json
import os
import re
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gen_keymap_image import load_font, wrap_text  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

KB_JSON = os.path.join(ROOT, "keyboards/sofle_pico/keyboard.json")
GEN_C = os.path.join(ROOT, ".build/obj_sofle_pico_default/src/default_keyboard.c")
OUT_PNG = os.path.join(HERE, "led_map.png")
OUT_SVG = os.path.join(HERE, "led_map.svg")

SCALE = 2
if len(sys.argv) > 1:
    SCALE = max(1, int(sys.argv[1]))

LED_FLAG_UNDERGLOW = 0x02
LED_FLAG_KEYLIGHT = 0x04
LED_FLAG_INDICATOR = 0x08

# --------------------------------------------------------------------------
# 数据 + 核对
# --------------------------------------------------------------------------


def load_data():
    kb = json.load(open(KB_JSON))
    rgb = kb["rgb_matrix"]
    leds = [
        {"i": i, "matrix": tuple(e["matrix"]), "x": e["x"], "y": e["y"], "flags": e.get("flags", 0)}
        for i, e in enumerate(rgb["layout"])
    ]
    keys = {tuple(k["matrix"]): k for k in kb["layouts"]["LAYOUT"]["layout"]}
    split = rgb.get("split_count", [len(leds), 0])
    return kb, rgb, leds, keys, split


def check_against_build(leds, split):
    """和已编译的 default 固件产物核对，避免图跟真正烧进去的固件不一致。"""
    if not os.path.exists(GEN_C):
        return None
    body = open(GEN_C, encoding="utf-8").read().split("led_config_t g_led_config = {", 1)[1]
    body = body.split("\n};", 1)[0]
    row_re = re.compile(r"\s*\{\s*(?:NO_LED|\d+)(?:\s*,\s*(?:NO_LED|\d+))*\s*\},?\s*")
    lines = body.splitlines()
    # 坐标行（一行里好几个 {x, y}）之后才是 flags 行；矩阵行在它前面
    cut = next((i for i, l in enumerate(lines) if l.count("{") >= 2), len(lines))
    mat = []
    for line in lines[:cut]:
        if row_re.fullmatch(line):
            cells = [c.strip() for c in line.strip().strip("{},").split(",") if c.strip()]
            mat.append([None if c == "NO_LED" else int(c) for c in cells])
    points = [(int(a), int(b)) for a, b in re.findall(r"\{\s*(\d+),\s*(\d+)\}", body)]
    flags_line = [l for l in lines[cut:] if re.fullmatch(r"\s*\{[\s\d,]+\},?\s*", l)]
    flags = [int(v) for v in flags_line[-1].strip().strip("{},").split(",")] if flags_line else []

    problems = []
    for led in leds:
        r, c = led["matrix"]
        if mat[r][c] != led["i"]:
            problems.append(f"matrix_co[{r}][{c}] = {mat[r][c]}，json 里是 {led['i']}")
    for led, (x, y) in zip(leds, points):
        if (x, y) != (led["x"], led["y"]):
            problems.append(f"LED {led['i']} 坐标 {x},{y} != json {led['x']},{led['y']}")
    live = [v for row in mat for v in row if v is not None]
    if len(live) != len(leds):
        problems.append(f"固件里 {len(live)} 颗灯，json 里 {len(leds)} 颗")
    if flags and set(flags) != {LED_FLAG_KEYLIGHT}:
        problems.append(f"flags 不是全 KEYLIGHT：{sorted(set(flags))}")
    if len(mat) != 10 or any(len(r) != 6 for r in mat):
        problems.append(f"矩阵形状异常：{len(mat)} 行")
    return problems


# --------------------------------------------------------------------------
# 几何：RGB 坐标（0..224 / 0..70 的基础单位）
# --------------------------------------------------------------------------

SC = 3.0         # 1 个 RGB 坐标单位 -> 3 个绘图单位
SPLIT_GAP = 96   # 两半之间额外留白（真实坐标里两半只差 4）
PAD = 36
KEY_W = 50
KEY_H = 36
Y_OFF = 0        # 标题占掉多少高之后，键盘才开画（build() 里算）
W = int(2 * PAD + 224 * SC + SPLIT_GAP + 64)   # 画布宽（放得下标题和说明）
X_OFF = (W - (2 * PAD + 224 * SC + SPLIT_GAP)) / 2
BODY_W = W - 2 * PAD - 28                      # 文字折行宽度
_PROBE = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def half_of(i, split):
    return 0 if i < split[0] else 1


def px(led, split):
    return PAD + X_OFF + led["x"] * SC + (SPLIT_GAP if half_of(led["i"], split) else 0)


def py(led):
    return Y_OFF + led["y"] * SC


def key_box(led, keys, split):
    k = keys.get(led["matrix"]) or {}
    h = KEY_H + (KEY_H * 0.5 if k.get("h", 1) > 1 else 0)
    return px(led, split) - KEY_W / 2, py(led) - KEY_H / 2, KEY_W, h


def ramp(local, total, sat, val):
    t = local / max(1, total - 1)
    r, g, b = colorsys.hsv_to_rgb(0.58 + 0.34 * t, sat, val)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


# --------------------------------------------------------------------------
# 图元
# --------------------------------------------------------------------------


def build(leds, keys, split, n_effects, problems, default, max_brightness):
    global Y_OFF
    prims = []
    left = [l for l in leds if half_of(l["i"], split) == 0]
    right = [l for l in leds if half_of(l["i"], split) == 1]

    # 标题：先量高度，键盘再往下排
    title = "Sofle Pico · 逐键 RGB 灯位图（default / split-left / split-right 固件）"
    subtitle = ("方块 = 一个按键；格子里大数字 = 固件里的 LED 全局索引；左上角 L/R＋数字 = 本半灯带的第几颗；"
                "左下角 [行,列] = 矩阵位置")
    t_size = next((sz for sz in (28, 26, 24, 22, 20)
                   if _PROBE.textlength(title, font=load_font(sz)) <= BODY_W), 20)
    y = 24
    prims.append(("text", PAD, y, title, t_size, "#1f2933", "lt"))
    y += int(t_size * 1.25)
    for line in wrap_text(_PROBE, subtitle, load_font(15), BODY_W):
        prims.append(("text", PAD, y, line, 15, "#52606d", "lt"))
        y += 21
    Y_OFF = y + 66

    # 两半的底板
    panels = []
    for half, name in ((left, "左手"), (right, "右手")):
        xs = [px(l, split) for l in half]
        ys = [py(l) for l in half]
        box = (min(xs) - KEY_W / 2 - 18, min(ys) - KEY_H / 2 - 46,
               max(xs) + KEY_W / 2 + 18, max(ys) + KEY_H + 26)
        panels.append(box)
        prims.append(("rect", box[0], box[1], box[2] - box[0], box[3] - box[1],
                      14, "#ffffff", "#d7dce3", 1))
        label = (f"{name} · {len(half)} 颗 · LED 索引 {half[0]['i']}–{half[-1]['i']}"
                 f"（灯带第 0–{len(half) - 1} 颗）")
        avail = box[2] - box[0] - 36
        size = next((sz for sz in (18, 17, 16, 15, 14, 13)
                     if _PROBE.textlength(label, font=load_font(sz)) <= avail), 13)
        prims.append(("text", (box[0] + box[2]) / 2, box[1] + 15, label, size, "#1f2933", "ct"))

    # 中间：TRRS 分隔线
    mid = PAD + X_OFF + 117 * SC + SPLIT_GAP / 2
    top_y, bot_y = panels[0][1] + 24, panels[0][3] - 24
    yy = top_y
    while yy < bot_y:
        prims.append(("rect", mid, yy, 2, 12, 1, "#c9ced6", "#c9ced6", 0))
        yy += 22

    # 1) 灯带连线（画在方块底下，只在缝隙里露出来）
    for half, base in ((left, 0), (right, split[0])):
        pts = [(px(l, split), py(l)) for l in half]
        for a, b in zip(pts, pts[1:]):
            prims.append(("line", a[0], a[1], b[0], b[1], 5, "#f5cba7", 1))

    # 2) 按键方块
    for l in leds:
        # split_count 是 [左半颗数, 右半颗数]，不是 [起点, 终点]
        is_left = half_of(l["i"], split) == 0
        base = 0 if is_left else split[0]
        n = split[0] if is_left else split[1]
        local = l["i"] - base
        x0, y0, w, h = key_box(l, keys, split)
        prims.append(("rect", x0, y0, w, h, 8, ramp(local, n, 0.20 + 0.55 * local / (n - 1), 1.0),
                      "#8a94a6", 1))
        prims.append(("text", x0 + w / 2, y0 + h / 2 - 4, str(l["i"]), 19, "#1f2933", "ct"))
        prims.append(("text", x0 + 5, y0 + 4, ("L" if base == 0 else "R") + str(local),
                      10, "#5b6470", "lt"))
        r, c = l["matrix"]
        prims.append(("text", x0 + 5, y0 + h - 15, f"[{r},{c}]", 10, "#5b6470", "lt"))
        # 链条首尾加粗框
        if local == 0:
            prims.append(("rect", x0 - 3, y0 - 3, w + 6, h + 6, 10, None, "#a04000", 2))
        if local == n - 1:
            prims.append(("rect", x0 - 3, y0 - 3, w + 6, h + 6, 10, None, "#34495e", 2))

    # 3) 缝隙里的箭头（指链条下一颗）
    for half in (left, right):
        pts = [(px(l, split), py(l)) for l in half]
        for a, b in zip(pts, pts[1:]):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = max(1e-6, (dx * dx + dy * dy) ** 0.5)
            ux, uy = dx / ln, dy / ln
            nx, ny = -uy, ux
            prims.append(("poly", [(mx + ux * 7, my + uy * 7),
                                   (mx - ux * 4 + nx * 5, my - uy * 4 + ny * 5),
                                   (mx - ux * 4 - nx * 5, my - uy * 4 - ny * 5)],
                          "#d35400", None, 0))

    # 5) 分隔线说明 + 图例（先折行量高度，再画框，最后写文字）
    lx = PAD
    lw = W - 2 * PAD
    y = panels[0][3] + 20
    caption = "两条虚线之间是 TRRS 串口：它只同步按键、层和灯效设置（模式/颜色/亮度/开关）；两半的灯带各自独立，各 29 颗，各自由自己那半的 GP0 驱动。"
    for line in wrap_text(_PROBE, caption, load_font(14), lw):
        prims.append(("text", lx, y, line, 14, "#8a94a6", "lt"))
        y += 20
    ly = y + 26
    notes = [
        f"数量：一共 {len(leds)} 颗，左右各 {split[0]} 颗；每颗都是「按键灯」（flags = 0x04 KEYLIGHT），没有底灯、没有指示灯。",
        "类型：WS2812 兼容的可寻址 RGB（WS2812 / SK6812 都是这一族，具体型号看你买的物料）。构建时带 -DRGB_MATRIX_ENABLE -DRGB_MATRIX_WS2812 -DWS2812_VENDOR。",
        "接法：每一半一条独立灯带，数据脚都是 GP0。橙色粗框 = 灯带第 1 颗（GP0 从这里进），深色粗框 = 灯带末端；箭头 = 数据走向。",
        f"渲染：两半各画自己那 {split[0]} 颗；模式/颜色/亮度/开关由 master 经 TRRS 同步过去（quantum/split_common/transactions.c PUT_RGB_MATRIX）。",
        f"默认：开机就亮（RGB_MATRIX_DEFAULT_ON）——纯白常亮（灯效 {default.get('animation', '?')}、"
        f"色相 {default.get('hue', 0)}、饱和 {default.get('sat', 255)}、亮度上限 {max_brightness}/255、速度 {default.get('speed', '?')}），"
        f"共启用 {n_effects} 种效果；只有 EEPROM 里存过 VIA 的关灯状态（或按过 RM_TOGG）才会不亮。",
        "控制：全在 ADJUST 层——左手上排 = 灯开关/切灯效/亮度±，右手上排 = 色相±/饱和±/速度±，下排最左 4~5 列 = 9 个灯效直达键（第一个是纯白常亮）；"
        "这一层两个旋钮也改成调灯（左=亮度、右=速度），按压键 = 灯开关 / 下一个灯效。其它层旋钮照旧是音量/切歌；"
        "USB 挂起时自动熄灯（RGB_DISABLE_WHEN_USB_SUSPENDED）。",
        "两个旋钮按压键 [4,5] / [9,5] 在固件里是 NO_LED —— 那两个位置没有灯珠。",
        "注：右手 [9,4] / [9,3]（R33 / R34）的坐标在上游 keyboard.json 里只差 10，其它相邻键差 19，所以图上这两个方块是叠着的。",
    ]
    if problems:
        notes.insert(0, "⚠ 与已编译固件核对不一致：" + "；".join(problems[:3]))
    wrapped = [(n, wrap_text(_PROBE, n, load_font(14), lw - 24)) for n in notes]
    legend_h = 56 + sum(20 * len(lines) for _, lines in wrapped) + 46
    prims.append(("rect", lx - 12, ly - 18, lw + 24, legend_h, 12, "#ffffff", "#d7dce3", 1))
    prims.append(("text", lx, ly, "这版固件里的灯，到底是什么", 18, "#1f2933", "lt"))
    yy = ly + 34
    for _, lines in wrapped:
        for line in lines:
            prims.append(("text", lx, yy, line, 14, "#52606d", "lt"))
            yy += 20

    prims.append(("rect", lx, yy + 6, 52, 26, 6, "#f1f3f5", "#c9ced6", 1))
    prims.append(("text", lx + 26, yy + 19, "无灯", 12, "#9aa5b1", "ct"))
    prims.append(("text", lx + 66, yy + 12, "= 矩阵里有按键、但没有灯珠的位置（两颗旋钮的按压键）",
                  14, "#52606d", "lt"))
    yy += 48

    H = int(yy + 52)
    return prims, W, H


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------


def emit_png(prims, W, H, path, scale):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (int(round(W * scale)), int(round(H * scale))), "#eef1f5")
    d = ImageDraw.Draw(img)
    for p in prims:
        if p[0] == "rect":
            _, x, y, w, h, r, fill, outline, lwd = p
            d.rounded_rectangle([x * scale, y * scale, (x + w) * scale, (y + h) * scale],
                                radius=r * scale, fill=fill,
                                outline=outline, width=max(1, int(round(lwd * scale))) if lwd else 0)
        elif p[0] == "line":
            _, x1, y1, x2, y2, lwd, color, _ = p
            d.line([x1 * scale, y1 * scale, x2 * scale, y2 * scale], fill=color,
                   width=max(1, int(round(lwd * scale))))
        elif p[0] == "poly":
            _, pts, fill, outline, lwd = p
            d.polygon([(x * scale, y * scale) for x, y in pts], fill=fill)
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
            _, x, y, w, h, r, fill, outline, lwd = p
            stroke = f' stroke="{outline}" stroke-width="{lwd}"' if lwd else ""
            body = f'fill="{fill}"' if fill else 'fill="none"'
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
                       f'{body}{stroke}/>')
        elif p[0] == "line":
            _, x1, y1, x2, y2, lwd, color, _ = p
            out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                       f'stroke="{color}" stroke-width="{lwd}" stroke-linecap="round"/>')
        elif p[0] == "poly":
            _, pts, fill, outline, lwd = p
            pts_s = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            out.append(f'<polygon points="{pts_s}" fill="{fill}"/>')
        else:
            _, x, y, s, size, fill, anchor = p
            pos = ('text-anchor="middle" dominant-baseline="central"' if anchor == "ct"
                   else 'dominant-baseline="hanging"')
            out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" {pos}>'
                       f'{html.escape(s)}</text>')
    out.append("</svg>")
    open(path, "w").write("\n".join(out) + "\n")
    return path


def main():
    kb, rgb, leds, keys, split = load_data()
    problems = check_against_build(leds, split)
    prims, W, H = build(leds, keys, split, len(rgb["animations"]), problems,
                        rgb["default"], rgb["max_brightness"])
    emit_png(prims, W, H, OUT_PNG, SCALE)
    emit_svg(prims, W, H, OUT_SVG)
    print(f"LED 总数 {len(leds)}（左 {split[0]} / 右 {split[1]}），"
          f"KEYLIGHT {sum(1 for l in leds if l['flags'] == LED_FLAG_KEYLIGHT)} 颗，"
          f"其他 flags {sorted({l['flags'] for l in leds} - {LED_FLAG_KEYLIGHT})}")
    print(f"默认灯效 {rgb['default']['animation']}、速度 {rgb['default']['speed']}，"
          f"亮度上限 {rgb['max_brightness']}，启用效果 {len(rgb['animations'])} 种")
    if problems is None:
        print("与已编译固件核对：跳过（没找到 .build 产物）")
    elif problems:
        print(f"与已编译固件核对：发现 {len(problems)} 处不一致 {problems[:3]}")
    else:
        print("与已编译固件核对：一致")
    print(f"写出 {OUT_PNG} / {OUT_SVG}（{W}x{H} 绘图单位，PNG 放大 {SCALE} 倍）")


if __name__ == "__main__":
    main()
