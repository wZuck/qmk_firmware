#!/usr/bin/env python3
"""生成 sofle_pico OLED 实际显示内容预览图。

它不是截图，而是按 keymap.c 的绘图代码逐字节重放一遍：
  * 字体取自驱动真正用的 drivers/oled/glcdfont.c（6x8，每字符 6 字节，LSB 在上）
  * 大字取自 keymap 自己生成的 oled_bigfont.h（12x16）
  * 动画取自 oled_anim.h 的 8 帧原始数据
  * 坐标规则与驱动一致：buffer[page * 64 + x]，bit (y % 8)，LSB = 最上面一行
见 drivers/oled/oled_driver.c 的 oled_write_pixel() / oled_set_cursor()。

产物（与本脚本同目录）：
  1x/   64x128 真实像素，面板上就是这样
  4x/   256x512 放大版，方便观看
  right_anim.gif   右半动画的 8 帧循环（4x）
  oled_overview.png 一图看全：左半 6 种状态 + 右半 8 帧

用法： python3 gen_oled_preview.py
"""

import os
import re

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KM_DIR = os.path.join(ROOT, "keyboards/sofle_pico/keymaps/default")
GLCDFONT = os.path.join(ROOT, "drivers/oled/glcdfont.c")
ANIM_H = os.path.join(KM_DIR, "oled_anim.h")
SNOW_H = os.path.join(KM_DIR, "oled_snow.h")
ANIM_INV_H = os.path.join(KM_DIR, "oled_anim_inv.h")
BIGFONT_H = os.path.join(KM_DIR, "oled_bigfont.h")
KEYMAP_C = os.path.join(KM_DIR, "keymap.c")

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"

W, H = 64, 128          # 旋转后的逻辑画布：64 宽 x 128 高
PAGE_BYTES = W          # 每个 page 64 字节
FONT_W, FONT_H = 6, 8   # 驱动字体

ON = (170, 232, 255)    # 点亮像素（SSD1306 常见的青白色）
OFF = (8, 12, 16)


# --------------------------------------------------------------------------
# 解析各种表
# --------------------------------------------------------------------------


def strip_comments(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def parse_glcdfont(path):
    """驱动字体：每字符 6 字节，每字节一列，bit0 = 顶部。"""
    body = strip_comments(open(path).read())
    body = body[body.index("{") : body.rindex("}")]
    vals = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", body)]
    return {c: vals[c * FONT_W : (c + 1) * FONT_W] for c in range(len(vals) // FONT_W)}


def parse_bigfont(path):
    """oled_bigfont.h：index 字符串 + 每个字形 24 字节（2 page x 12 列）。"""
    src = open(path).read()
    index = re.search(r'oled_bigfont_index\[\]\s*=\s*"([^"]*)"', src).group(1)
    body = src[src.index("oled_bigfont[") :]
    glyphs = []
    for grp in re.findall(r"\{([^{}]*)\}", body):
        vals = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", grp)]
        if len(vals) == 24:
            glyphs.append(vals)
    return index, glyphs


def parse_anims(path, array="oled_anim"):
    """oled_anim.h / oled_anim_inv.h：SOFLE_ANIM_COUNT 组动画，每组 N 帧、每帧 1024 字节。

    返回 [(名字, [帧...]), ...]，名字取自生成器写在每组前面的 "// name"。
    `array` 用来选正色（oled_anim）还是反色（oled_anim_inv）那张表。
    """
    src = open(path).read()
    body = src[src.index(array + "[") :]
    anims = []
    for name, block in re.findall(r"\{\s*//\s*([a-z_]+)\s*\n(.*?)\n    \},", body, flags=re.S):
        frames = []
        for grp in re.findall(r"\{\s*//\s*frame \d+\s*(.*?)\n\s*\},", block, flags=re.S):
            vals = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", grp)]
            if vals:
                frames.append(vals)
        anims.append((name, frames))
    return anims


def parse_snow(path, array="oled_snow"):
    """oled_snow.h 里的一个表：SOFLE_SNOW_FRAMES 帧、每帧 1024 字节。

    和 oled_anim.h 同一个格式，只是没有"每组"这一层——它是单独的一个画面
    （OLED 键循环里的 snow / snow 反色）。`array` 选正色还是反色那张表。
    """
    src = open(path).read()
    body = src[src.index(array + "[") :]
    body = body[: body.index("};")]
    frames = []
    for grp in re.findall(r"\{\s*//\s*frame \d+\s*(.*?)\n\s*\},", body, flags=re.S):
        vals = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", grp)]
        if vals:
            frames.append(vals)
    return frames


# --------------------------------------------------------------------------
# 画布：与驱动同样的内存布局
# --------------------------------------------------------------------------


class Canvas:
    def __init__(self):
        self.buf = bytearray(W * H // 8)

    def raw(self, line, x, data):
        """等价于 oled_set_cursor(x, line) + oled_write_raw()，x 以字节计。"""
        base = line * PAGE_BYTES
        for i, b in enumerate(data):
            if base + x + i < len(self.buf):
                self.buf[base + x + i] = b

    def text(self, line, s, font):
        """等价于 oled_set_cursor(0, line) + oled_write()：每字符 6 列。"""
        for n, ch in enumerate(s):
            glyph = font.get(ord(ch), [0] * FONT_W)
            for i, b in enumerate(glyph):
                x = n * FONT_W + i
                if x < W:
                    self.buf[line * PAGE_BYTES + x] = b

    def banner(self, line, s, bigfont):
        index, glyphs = bigfont
        total = len(s) * 12
        x = (W - total) // 2
        for ch in s:
            if ch not in index:
                x += 12
                continue
            g = glyphs[index.index(ch)]
            for page in range(2):
                for i in range(12):
                    if 0 <= x + i < W:
                        self.buf[(line + page) * PAGE_BYTES + x + i] = g[page * 12 + i]
            x += 12

    def to_image(self, scale=1, on=ON, off=OFF):
        img = Image.new("RGB", (W, H), off)
        px = img.load()
        for page in range(H // 8):
            for x in range(W):
                byte = self.buf[page * PAGE_BYTES + x]
                for bit in range(8):
                    if byte >> bit & 1:
                        px[x, page * 8 + bit] = on
        if scale != 1:
            img = img.resize((W * scale, H * scale), Image.NEAREST)
        return img


# --------------------------------------------------------------------------
# 复刻 keymap.c 的 render_status()
# --------------------------------------------------------------------------

LINE_RULE_TOP, LINE_BANNER, LINE_RULE_BOTTOM = 1, 2, 4
LINE_MODE, LINE_MODS, LINE_PEAK, LINE_WPM, LINE_WPM_BAR, LINE_CAPS = 6, 7, 8, 9, 10, 13


def status_screen(banner_text, mode_text, mods_text, peak, wpm, caps, font, bigfont):
    c = Canvas()
    c.raw(LINE_RULE_TOP, 0, [0x80] * W)                     # render_rule(top, bottom_edge)
    c.banner(LINE_BANNER, banner_text, bigfont)
    c.raw(LINE_RULE_BOTTOM, 0, [0x01] * W)                  # render_rule(bottom, top_edge)
    c.text(LINE_MODE, mode_text, font)
    c.text(LINE_MODS, "MODS " + mods_text, font)            # 每格：按住显示字母，否则 '.'

    peak_text = "PEAK    %d%d" % (min(peak, 99) // 10, min(peak, 99) % 10)
    c.text(LINE_PEAK, peak_text, font)

    shown = min(wpm, 99)
    c.text(LINE_WPM, "WPM    %d%d" % (shown // 10, shown % 10), font)

    first, last = 5, W - 5
    filled = (last - first) if wpm >= 100 else wpm * (last - first) // 100
    bar = bytearray(W)
    for x in range(first, last):
        bar[x] = 0x40
    for x in range(first, first + filled):
        bar[x] = 0x7E
    c.raw(LINE_WPM_BAR, 0, bar)

    c.text(LINE_CAPS, "CAPS ON  " if caps else "CAPS OFF ", font)
    return c


# 状态屏的几种典型画面
# (name, caption, (banner, mode, mods, peak, wpm, caps))
LEFT_STATES = [
    ("status_01_idle_win", "空闲 · Win 模式 · 无修饰键", ("BASE", "MODE WIN ", "....", 0, 0, False)),
    ("status_02_typing_wpm42", "打字中 · WPM 42 · 峰值 58", ("BASE", "MODE WIN ", "....", 58, 42, False)),
    ("status_03_mac_wpm76", "Mac 模式 · 按住 Alt · WPM 76 · 峰值 92", ("BASE", "MODE MAC ", "..A.", 92, 76, False)),
    ("status_04_layer_lower_wpm55", "按住 LOWER · 按住 Shift · WPM 55", ("LOWER", "MODE WIN ", ".S..", 74, 55, False)),
    ("status_05_layer_raise_wpm12", "按住 RAISE · 按住 Ctrl · WPM 12", ("RAISE", "MODE WIN ", "C...", 66, 12, False)),
    ("status_06_adjust_mac_wpm88_caps", "ADJUST · 四个修饰键全按 · Caps Lock 打开", ("ADJ", "MODE MAC ", "CSAG", 88, 88, True)),
]

# --------------------------------------------------------------------------
# 复刻 keymap.c 的 render_stats() / render_graph() / render_layers()
# --------------------------------------------------------------------------

GRAPH_SAMPLES = 21


def line_start(text, label):
    """keymap.c 里的同名辅助：9 个字符，标签靠左，其余补空格。"""
    s = list(" " * 9)
    for i, ch in enumerate(label):
        s[i] = ch
    return s


def right_digits(text, value, digits, end=8):
    v = min(value, 10**digits - 1)
    for i in range(digits):
        text[end - i] = chr(ord("0") + v % 10)
        v //= 10
    return text


def stats_screen(keys, wpm, peak, layer, hours, mins, caps, mode, font, bigfont):
    c = Canvas()
    c.raw(1, 0, [0x80] * W)
    c.banner(2, "STATS", bigfont)
    c.raw(4, 0, [0x01] * W)

    c.text(6, "".join(right_digits(line_start(None, "KEY"), keys, 5)), font)
    c.text(7, "".join(right_digits(line_start(None, "WPM"), wpm, 2)), font)
    c.text(8, "".join(right_digits(line_start(None, "PEAK"), peak, 2)), font)
    c.text(9, "".join(right_digits(line_start(None, "LAYER"), layer, 1)), font)

    up = line_start(None, "UP")
    up[4], up[5] = str((hours // 10) % 10), str(hours % 10)
    up[6] = ":"
    up[7], up[8] = str((mins % 60) // 10), str((mins % 60) % 10)
    c.text(10, "".join(up), font)

    c.text(13, "CAPS ON  " if caps else "CAPS OFF ", font)
    mode = "MODE MAC " if mode == "MAC" else "MODE WIN "
    c.text(14, mode, font)
    return c


def graph_screen(history, font, bigfont):
    """history 是 21 个采样（旧的在前），和自己维护的历史一致。"""
    c = Canvas()
    wpm = min(history[-1], 99)
    c.raw(1, 0, [0x80] * W)
    c.banner(2, "%02d" % wpm, bigfont)
    c.text(6, "WPM      ", font)

    chart_line, chart_h = 9, H - 9 * 8
    for page in range(chart_h // 8):
        row = bytearray(W)
        for i, val in enumerate(history):
            height = val * chart_h // 100
            for w in range(2):
                x = 1 + i * 3 + w
                if x >= W:
                    continue
                for bit in range(8):
                    y = chart_line * 8 + page * 8 + bit
                    if H - 1 - y < height:
                        row[x] |= 1 << bit
        c.raw(chart_line + page, 0, row)
    return c


def layers_screen(active, mode, font, bigfont):
    c = Canvas()
    c.raw(1, 0, [0x80] * W)
    c.banner(2, "LAYER", bigfont)
    c.raw(4, 0, [0x01] * W)

    for i, name in enumerate(("BASE", "LOWER", "RAISE", "ADJ")):
        state = "ON" if i in active else "OFF"
        text = line_start(None, name)
        pad = 9 - len(name) - len(state)
        for k, ch in enumerate(state):
            text[len(name) + pad + k] = ch
        c.text(6 + i, "".join(text), font)

    c.text(13, "MODE MAC " if mode == "MAC" else "MODE WIN ", font)
    return c


# 三种信息屏的典型画面
STATS_STATES = [
    ("stats_01_fresh", "刚上电：0 键 · 层 0 · 运行 0 分钟",
     dict(keys=0, wpm=0, peak=0, layer=0, hours=0, mins=0, caps=False, mode="WIN")),
    ("stats_02_busy", "用了一会儿：KEY 12345 · WPM 62 · 峰值 88 · 层 1 · 运行 3:21 · Caps 开",
     dict(keys=12345, wpm=62, peak=88, layer=1, hours=3, mins=21, caps=True, mode="WIN")),
]

GRAPH_STATES = [
    ("graph_01_idle", "空闲：21 秒里没有输入，曲线贴底",
     [0] * GRAPH_SAMPLES),
    ("graph_02_typing", "打字中：先热身再掉速，最后两秒回到 74",
     [0, 0, 12, 35, 48, 60, 52, 44, 70, 82, 74, 60, 0, 0, 25, 45, 58, 66, 74, 78, 74]),
]

LAYER_STATES = [
    ("layers_01_base", "只有基础层（QWERTY）", {0}),
    ("layers_02_lower", "按住左拇指 LOWER", {0, 1}),
    ("layers_03_adjust", "LOWER + RAISE 同时按住 → ADJUST", {0, 3}),
]


def load_font(size):
    return ImageFont.truetype(FONT_PATH, size)


def parse_anim_titles(path):
    """从 oled_anim.h 的头部注释取 (名字, 说明)，图上的说明就跟着生成器走。"""
    out = []
    for line in open(path):
        m = re.match(r"//\s+\d+\s+(\w+)\s+-\s+(.*)", line)
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def png(sc, sub, name):
    return os.path.join(HERE, sub, name + ".png")


def main():
    font = parse_glcdfont(GLCDFONT)
    bigfont = parse_bigfont(BIGFONT_H)
    anims = parse_anims(ANIM_H)
    titles = dict(parse_anim_titles(ANIM_H))
    nframes = len(anims[0][1])
    snow = parse_snow(SNOW_H)
    print(f"字体 {len(font)} 字符；大字 {len(bigfont[1])} 字形；动画 {len(anims)} 组 x {nframes} 帧 x {len(anims[0][1][0])} 字节"
          f"；雪人 {len(snow)} 帧 x {len(snow[0])} 字节")

    for d in ("1x", "4x"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
        # 旧版本的图（left_* / right_anim* / anim_NN）直接清掉，避免新旧混在一起
        for f in os.listdir(os.path.join(HERE, d)):
            if f.endswith((".png", ".gif")):
                os.remove(os.path.join(HERE, d, f))
    for f in os.listdir(HERE):
        if f.endswith(".gif"):
            os.remove(os.path.join(HERE, f))

    # ① status 状态屏
    made = []
    for name, desc, (banner, mode, mods, peak, wpm, caps) in LEFT_STATES:
        c = status_screen(banner, mode, mods, peak, wpm, caps, font, bigfont)
        c.to_image(1).save(png(1, "1x", name))
        c.to_image(4).save(png(4, "4x", name))
        made.append((name, desc))

    # ② 另外三种信息屏：stats / graph / layers
    info = []
    for name, desc, kw in STATS_STATES:
        c = stats_screen(font=font, bigfont=bigfont, **kw)
        c.to_image(1).save(png(1, "1x", name))
        c.to_image(4).save(png(4, "4x", name))
        info.append((name, desc))
    for name, desc, hist in GRAPH_STATES:
        c = graph_screen(hist, font, bigfont)
        c.to_image(1).save(png(1, "1x", name))
        c.to_image(4).save(png(4, "4x", name))
        info.append((name, desc))
    for name, desc, active in LAYER_STATES:
        c = layers_screen(active, "WIN", font, bigfont)
        c.to_image(1).save(png(1, "1x", name))
        c.to_image(4).save(png(4, "4x", name))
        info.append((name, desc))

    # ③ 动画：每组的帧图 + 一个 GIF
    anim_rows = []
    for aname, frames in anims:
        imgs = []
        for i, frame in enumerate(frames):
            c = Canvas()
            c.buf[:] = bytes(frame)
            c.to_image(1).save(png(1, "1x", f"anim_{aname}_{i:02d}"))
            imgs.append(c.to_image(4))
            imgs[-1].save(png(4, "4x", f"anim_{aname}_{i:02d}"))
        imgs[0].save(os.path.join(HERE, f"anim_{aname}.gif"), save_all=True,
                     append_images=imgs[1:], duration=125, loop=0, optimize=False)
        anim_rows.append((aname, titles.get(aname, ""), [im.resize((W * 2, H * 2), Image.NEAREST) for im in imgs]))

    # ④ 雪人（oled_snow.h）：两帧 + 一个 GIF。它不是按键切出来的，而是 OLED 键循环里的
    #    一个画面（排在四组反色动画之后），所以单独一栏展示，也单独出一张两帧对比图。
    snow_imgs = []
    for i, frame in enumerate(snow):
        c = Canvas()
        c.buf[:] = bytes(frame)
        c.to_image(1).save(png(1, "1x", f"snow_{i:02d}"))
        img = c.to_image(4)
        img.save(png(4, "4x", f"snow_{i:02d}"))
        snow_imgs.append(img)
    snow_imgs[0].save(os.path.join(HERE, "snow_pair.gif"), save_all=True,
                      append_images=snow_imgs[1:], duration=250, loop=0, optimize=False)
    pair = Image.new("RGB", (W * 4 * len(snow_imgs) + 20 * (len(snow_imgs) - 1), H * 4), "#f2f4f7")
    for i, img in enumerate(snow_imgs):
        pair.paste(img, (i * (W * 4 + 20), 0))
    pair.save(os.path.join(HERE, "snow_pair.png"))

    # ⑤ 反色（白天）版本：雪人的反色两帧，下面那一行拼一张正/反对照图
    snow_inv = parse_snow(SNOW_H, "oled_snow_inv")
    snow_inv_imgs = []
    for i, frame in enumerate(snow_inv):
        c = Canvas()
        c.buf[:] = bytes(frame)
        c.to_image(1).save(png(1, "1x", f"snow_inv_{i:02d}"))
        img = c.to_image(4)
        img.save(png(4, "4x", f"snow_inv_{i:02d}"))
        snow_inv_imgs.append(img)
    snow_inv_imgs[0].save(os.path.join(HERE, "snow_pair_inv.gif"), save_all=True,
                          append_images=snow_inv_imgs[1:], duration=250, loop=0, optimize=False)
    both = Image.new("RGB", (W * 4 * 4 + 20 * 3, H * 4), "#f2f4f7")
    for i, img in enumerate(snow_imgs + snow_inv_imgs):
        both.paste(img, (i * (W * 4 + 20), 0))
    both.save(os.path.join(HERE, "snow_polarities.png"))

    # 吉祥物的正/反对照（反色那套的四组动画，各取第一帧）
    anim_inv = parse_anims(ANIM_INV_H, "oled_anim_inv")
    mascot_both = Image.new("RGB", (W * 2 * 4 + 12 * 3, H * 2 * 2 + 12), "#f2f4f7")
    for k, (name, frames) in enumerate(anims):
        c = Canvas(); c.buf[:] = bytes(frames[0])
        mascot_both.paste(c.to_image(2), (k * (W * 2 + 12), 0))
    for k, (name, frames) in enumerate(anim_inv):
        c = Canvas(); c.buf[:] = bytes(frames[0])
        mascot_both.paste(c.to_image(2), (k * (W * 2 + 12), H * 2 + 12))
    mascot_both.save(os.path.join(HERE, "mascot_polarities.png"))

    # 总览图：一行 status（4x），下面动画按两列排（2x），最后一行是正/反两套对照
    pad, gap = 26, 22
    sc_w, sc_h = W * 4, H * 4            # 状态屏 4x
    af_w, af_h = W * 2, H * 2            # 动画帧 2x
    # 正/反两套各取第一帧拼一列，下面第 ⑤ 节要贴：上行正色（夜晚）、下行反色（白天）
    imgs_normal_pol = [Image.open(png(4, "4x", f"anim_{n}_{0:02d}")).resize((af_w, af_h), Image.NEAREST)
                       for n, _ in anims] + \
                      [Image.open(png(4, "4x", f"snow_{i:02d}")).resize((af_w, af_h), Image.NEAREST)
                       for i in range(len(snow))]
    imgs_inverted_pol = [Image.open(png(4, "4x", f"anim_{n}_{0:02d}")).resize((af_w, af_h), Image.NEAREST)
                         for n, _ in anim_inv] + \
                        [Image.open(png(4, "4x", f"snow_inv_{i:02d}")).resize((af_w, af_h), Image.NEAREST)
                         for i in range(len(snow_inv))]
    row_w = 8 * (af_w + 4) + 24          # 一组动画的宽度
    grid_w = 2 * (row_w + gap) - gap
    sheet_w = pad * 2 + max(6 * (sc_w + gap) - gap, grid_w, W * 4 * 2 + 20)
    row_h = 34 + af_h + 26
    info_cols = 4
    info_rows = (len(info) + info_cols - 1) // info_cols
    cells_count = len(anim_rows) + (1 if snow else 0)  # 四组动画 + 雪人
    anim_grid_rows = (cells_count + 1) // 2
    sheet_h = 128 + (sc_h + 52) + 34 + info_rows * (sc_h + 52) + 30 + anim_grid_rows * (row_h + 20) + 60 + 2 * (af_h + 26) + 60
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#f2f4f7")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 20), "Sofle Pico OLED 显示内容预览", font=load_font(30), fill="#1f2933")
    d.text((pad, 60), "每一半都能在 ADJUST 层用自己那侧的 OLED 键在 status / stats / graph / layers / 4 组动画(正+反) / 雪人(正+反) 之间循环",
           font=load_font(17), fill="#52606d")

    y = 122
    d.text((pad, y - 26), "① status 状态屏（默认：左手）—— 层名 / 模式 / 修饰键 / 峰值 / WPM / Caps",
           font=load_font(19), fill="#1a56b8")
    for i, (name, desc) in enumerate(made):
        x = pad + i * (sc_w + gap)
        sheet.paste(Image.open(png(4, "4x", name)), (x, y))
        d.rectangle([x - 1, y - 1, x + sc_w, y + sc_h], outline="#c9ced6")
        for n, line in enumerate(wrap(d, desc, load_font(14), sc_w)):
            d.text((x, y + sc_h + 8 + n * 18), line, font=load_font(14), fill="#52606d")

    y = y + sc_h + 52 + 34
    d.text((pad, y - 26), "② 另外三种信息屏：stats 统计 / graph WPM 曲线 / layers 层状态",
           font=load_font(19), fill="#1b7f4b")
    for i, (name, desc) in enumerate(info):
        col, row = i % info_cols, i // info_cols
        x = pad + col * (sc_w + gap)
        yy = y + row * (sc_h + 52)
        sheet.paste(Image.open(png(4, "4x", name)), (x, yy))
        d.rectangle([x - 1, yy - 1, x + sc_w, yy + sc_h], outline="#c9ced6")
        for n, line in enumerate(wrap(d, desc, load_font(14), sc_w)):
            d.text((x, yy + sc_h + 8 + n * 18), line, font=load_font(14), fill="#52606d")

    y = y + info_rows * (sc_h + 52) + 34
    d.text((pad, y - 26), "③ 动画（默认：右手第一组）—— 每组 8 帧、8 fps，另有独立的 GIF；"
                          "④ 雪人（oled_snow.h，正/反各 2 帧）排在四组反色动画之后",
           font=load_font(19), fill="#a85a06")
    snow_desc = "oled_snow.h（oled_snow1/2.pdf，2 帧）—— OLED 键循环里的 snow 画面"
    cells = ([(n, desc, imgs) for n, desc, imgs in anim_rows]
             + ([("snow_pair", snow_desc, [im.resize((W * 2, H * 2), Image.NEAREST) for im in snow_imgs])] if snow else [])
             )
    for k, (aname, desc, imgs) in enumerate(cells):
        col, row = k % 2, k // 2
        x = pad + col * (row_w + gap)
        yy = y + row * (row_h + 20)
        if aname == "snow_pair":
            label = f"④ 雪人：{aname}"
        else:
            label = f"anim {k + 1}/{len(anim_rows)}：{aname}"
        d.text((x, yy), label, font=load_font(16), fill="#1f2933")
        d.text((x + 150, yy + 2), desc, font=load_font(13), fill="#66727f")
        if imgs:
            for i, im in enumerate(imgs):
                sheet.paste(im, (x + i * (af_w + 4), yy + 26))

    # 最后一栏：正/反两套对照（上面小怪物四组、下面雪人两帧），一眼看出白天/夜晚两版
    y_pol = y + anim_grid_rows * (row_h + 20) + 10
    d.text((pad, y_pol - 26), "⑤ 反色版（白天模式）—— 上面一行正色（夜晚），下面一行反色；"
                             "两栏都是 OLED 键循环里的画面",
           font=load_font(19), fill="#7a3bb8")
    for k, im in enumerate(imgs_normal_pol):
        sheet.paste(im, (pad + k * (af_w + 4), y_pol))
        d.text((pad + k * (af_w + 4), y_pol + af_h + 2), "正色", font=load_font(13), fill="#52606d")
    for k, im in enumerate(imgs_inverted_pol):
        sheet.paste(im, (pad + k * (af_w + 4), y_pol + af_h + 22))
        d.text((pad + k * (af_w + 4), y_pol + 2 * af_h + 24), "反色", font=load_font(13), fill="#52606d")

    sheet.save(os.path.join(HERE, "oled_overview.png"))
    print("已生成:", os.path.join(HERE, "oled_overview.png"))
    print(f"状态屏 {len(made)} 张，信息屏 {len(info)} 张，动画 {len(anim_rows)} 组 x {nframes} 帧 + 雪人 {len(snow)} 帧(正/反)，GIF {len(anim_rows)} 个")


def wrap(d, text, font, max_w):
    """按像素宽度折行，优先在空格处断，避免把单词劈成两半。"""
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


if __name__ == "__main__":
    main()
