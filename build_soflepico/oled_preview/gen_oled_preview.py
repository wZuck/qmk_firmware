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


def parse_anim(path):
    """oled_anim.h：N 帧，每帧 1024 字节。"""
    src = open(path).read()
    frames = []
    for grp in re.findall(r"\{\s*//\s*frame \d+\s*(.*?)\n\s*\}", src, flags=re.S):
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

logo_name = "screen_logo"


def logo_screen():
    """oled_image.h：64x96 的图（12 个 page），下半屏留空。"""
    src = open(os.path.join(KM_DIR, "oled_image.h")).read()
    body = re.findall(r"0x([0-9A-Fa-f]{2})", src[src.index("{"):])
    vals = [int(v, 16) for v in body][: 12 * W]
    c = Canvas()
    c.raw(0, 0, vals)
    return c


def load_font(size):
    return ImageFont.truetype(FONT_PATH, size)


def main():
    font = parse_glcdfont(GLCDFONT)
    bigfont = parse_bigfont(BIGFONT_H)
    frames = parse_anim(ANIM_H)
    print(f"字体 {len(font)} 个字符；大字 {len(bigfont[1])} 个字形；动画 {len(frames)} 帧 x {len(frames[0])} 字节")

    for d in ("1x", "4x"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)

    # 清掉上一版命名留下的图（left_* / right_anim*），避免新旧混在一起
    for d in ("1x", "4x"):
        for f in os.listdir(os.path.join(HERE, d)):
            if f.startswith("left_") or f.startswith("right_anim"):
                os.remove(os.path.join(HERE, d, f))
    for f in ("right_anim.gif",):
        if os.path.exists(os.path.join(HERE, f)):
            os.remove(os.path.join(HERE, f))

    made = []
    for name, desc, (banner, mode, mods, peak, wpm, caps) in LEFT_STATES:
        c = status_screen(banner, mode, mods, peak, wpm, caps, font, bigfont)
        c.to_image(1).save(os.path.join(HERE, "1x", name + ".png"))
        c.to_image(4).save(os.path.join(HERE, "4x", name + ".png"))
        made.append((name, desc))

    # logo 画面（两边都能切到）
    logo = logo_screen()
    logo.to_image(1).save(os.path.join(HERE, "1x", logo_name + ".png"))
    logo_img = logo.to_image(4)
    logo_img.save(os.path.join(HERE, "4x", logo_name + ".png"))

    anim_imgs = []
    for i, frame in enumerate(frames):
        c = Canvas()
        c.buf[:] = bytes(frame)
        img = c.to_image(1)
        img.save(os.path.join(HERE, "1x", f"anim_{i:02d}.png"))
        anim_imgs.append(c.to_image(4))
        anim_imgs[-1].save(os.path.join(HERE, "4x", f"anim_{i:02d}.png"))
        # 旧的 right_anim_* 名字清掉，避免和上一版混淆
        for old in (f"right_anim_{i:02d}.png",):
            for sub in ("1x", "4x"):
                p = os.path.join(HERE, sub, old)
                if os.path.exists(p):
                    os.remove(p)

    # 动画 GIF
    anim_imgs[0].save(os.path.join(HERE, "anim.gif"), save_all=True,
                      append_images=anim_imgs[1:], duration=125, loop=0, optimize=False)
    if os.path.exists(os.path.join(HERE, "right_anim.gif")):
        os.remove(os.path.join(HERE, "right_anim.gif"))

    # 总览图
    pad, cap_h, gap = 26, 52, 22
    cols = max(len(LEFT_STATES), len(frames), 3)
    cell_w, cell_h = W * 4, H * 4
    sheet_w = pad * 2 + cols * (cell_w + gap) - gap
    sheet_h = pad * 3 + 60 + (cell_h + cap_h) * 3 + 60
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#f2f4f7")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 22), "Sofle Pico OLED 显示内容预览", font=load_font(30), fill="#1f2933")
    d.text((pad, 62), "每一半都能在 ADJUST 层用自己那侧的 OLED 键在三种画面之间切换；下面是三种画面的样子",
           font=load_font(17), fill="#52606d")

    y = 128
    d.text((pad, y - 28), "① status 状态屏（默认：左手）—— 层名 / 模式 / 修饰键 / 峰值 / WPM / Caps", font=load_font(19), fill="#1a56b8")
    for i, (name, desc) in enumerate(made):
        x = pad + i * (cell_w + gap)
        sheet.paste(Image.open(os.path.join(HERE, "4x", name + ".png")), (x, y))
        d.rectangle([x - 1, y - 1, x + cell_w, y + cell_h], outline="#c9ced6")
        for n, line in enumerate(wrap(d, desc, load_font(14), cell_w)):
            d.text((x, y + cell_h + 8 + n * 18), line, font=load_font(14), fill="#52606d")

    y = y + cell_h + cap_h + 46
    d.text((pad, y - 28), "② anim 动画（默认：右手） 8 帧循环，8 fps，弹跳 + 眨眼 + 摆手",
           font=load_font(19), fill="#a85a06")
    for i, img in enumerate(anim_imgs):
        x = pad + i * (cell_w + gap)
        sheet.paste(img, (x, y))
        d.rectangle([x - 1, y - 1, x + cell_w, y + cell_h], outline="#c9ced6")
        d.text((x, y + cell_h + 8), f"帧 {i + 1}", font=load_font(14), fill="#52606d")

    y = y + cell_h + cap_h + 46
    d.text((pad, y - 28), "③ logo 静态图", font=load_font(19), fill="#1b7f4b")
    x = pad
    sheet.paste(logo_img, (x, y))
    d.rectangle([x - 1, y - 1, x + cell_w, y + cell_h], outline="#c9ced6")
    d.text((x, y + cell_h + 8), "oled_image.h（64x96）", font=load_font(14), fill="#52606d")
    d.text((pad + cell_w + gap, y + 8),
           "两边都能切到；切换时固件会先清屏，所以不会留下上一屏的残影。",
           font=load_font(16), fill="#52606d")

    sheet.save(os.path.join(HERE, "oled_overview.png"))
    print("已生成:", os.path.join(HERE, "oled_overview.png"))
    print("状态屏画面:", len(made), " 动画帧:", len(frames), " logo: 1")


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
