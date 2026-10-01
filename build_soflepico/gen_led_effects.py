#!/usr/bin/env python3
"""把「原生灯效采集器」吐出来的逐帧 RGB 数据画成 GIF，并生成网页播放器要的数据。

数据来源是 `led_effects/led_frames.json`，由 `led_effects/harness.c` 在本机编译运行产生。
那份 C 程序直接编译 QMK 仓库里**真实的灯效源码**（quantum/rgb_matrix/animations/*.h），
所以这里的每一帧就是真机上那一刻会点亮的颜色，不是照着效果图临摹的。

产物（都与本脚本同目录）：
  led_effects/fx_<名字>.gif   每个灯效一段循环动画，可直接分享
  led_effects.js              网页互动播放器要的几何 + 逐帧数据（base64）

用法： python3 gen_led_effects.py [--scale 0.6] [--stride 2] [--colors 32]
                                [--frames-json led_effects/led_frames.json]
"""

import base64
import json
import os
import re
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

KB_JSON = os.path.join(ROOT, "keyboards/sofle_pico/keyboard.json")
LED_TABLES_C = os.path.join(ROOT, "quantum/led_tables.c")
FRAMES_JSON = os.path.join(HERE, "led_effects", "led_frames.json")
OUT_DIR = os.path.join(HERE, "led_effects")
JS_OUT = os.path.join(HERE, "led_effects.js")

from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

# --------------------------------------------------------------------------
# 几何：和 gen_led_map.py 用同一套换算，画出来才是同一块键盘
# --------------------------------------------------------------------------

SC = 3.0         # 1 个 RGB 坐标单位 = 3 个绘图单位
SPLIT_GAP = 96   # 两半之间额外留白（真实坐标里两半只差 4）
KEY_W = 50
KEY_H = 36
MARGIN = 22

BG = (10, 14, 18)        # 关灯的键盘底色
CAP = (23, 30, 38)       # 键帽
CAP_EDGE = (46, 58, 70)  # 键帽描边

# 灯效展示顺序 = keymap.c 里 FX_* 预设键的顺序
#   (采集器里的名字, keymap 里的键码, 中文名, 一句话说明)
# "solid_white" 不是采集器里的名字：纯白常亮是常量输出，由白色的帧直接算出来（见 WHITE_ID）
WHITE_ID = "solid_white"

EFFECTS = [
    (WHITE_ID, "FX_WHITE", "纯白常亮",
     "出厂默认。solid_color 灯效 + 饱和 0，58 颗灯一起白：hsv(0,0,127) 过 CIE1931 曲线 = RGB(47,47,47)。"),
    ("cycle_out_in", "FX_CYCLE_OUT_IN", "单色波扩散",
     "整块键盘同一个色相，按到键盘中心的距离决定相位，一圈圈向外推。"),
    ("hue_wave", "FX_HUE_WAVE", "彩虹波浪",
     "色相随 X 坐标偏移，像一道彩虹从左往右扫过。"),
    ("rainbow_beacon", "FX_RAINBOW_BEACON", "彩虹信标",
     "两道彩虹光柱绕着键盘中心旋转，像灯塔。"),
    ("pixel_flow", "FX_PIXEL_FLOW", "像素流",
     "颜色沿对角方向流动，一格一格地推过去。"),
    ("jellybean_raindrops", "FX_JELLYBEAN", "随机彩点",
     "每帧随机挑几颗灯换一个随机颜色，再慢慢暗下去，像撒糖豆。"),
    ("digital_rain", "FX_DIGITAL_RAIN", "数字雨",
     "一列列绿色光点从上往下落，落到头就换一列重新开始。"),
    ("solid_reactive_multinexus", "FX_REACTIVE_NEXUS", "按键涟漪",
     "从按下的那颗灯向四周扩散的光圈，多个按键可以叠加。"),
    ("typing_heatmap", "FX_TYPING_HEATMAP", "打字热图",
     "按过的位置亮起来，越按越亮，停下来后慢慢冷掉。"),
]

# 采集器可能用不同的名字（下划线/大小写），按关键字宽松匹配
ALIASES = {
    "cycle_out_in": ("cycle_out_in", "cycleoutin"),
    "hue_wave": ("hue_wave", "huewave"),
    "rainbow_beacon": ("rainbow_beacon", "rainbowbeacon", "beacon"),
    "pixel_flow": ("pixel_flow", "pixelflow"),
    "jellybean_raindrops": ("jellybean",),
    "digital_rain": ("digital_rain", "digitalrain"),
    "solid_reactive_multinexus": ("multinexus", "reactive_nexus", "nexus"),
    "typing_heatmap": ("typing_heatmap", "heatmap"),
}


def load_keyboard():
    kb = json.load(open(KB_JSON))
    rgb = kb["rgb_matrix"]
    leds = [
        {"i": i, "matrix": tuple(e["matrix"]), "x": e["x"], "y": e["y"]}
        for i, e in enumerate(rgb["layout"])
    ]
    keys = {tuple(k["matrix"]): k for k in kb["layouts"]["LAYOUT"]["layout"]}
    split = rgb.get("split_count", [len(leds), 0])
    return leds, keys, split, rgb


def build_geometry(leds, keys, split):
    """每颗灯的方块位置（绘图单位）。和 gen_led_map.py 同一套坐标。"""
    geom = []
    for led in leds:
        k = keys.get(led["matrix"]) or {}
        tall = 1.5 if k.get("h", 1) > 1 else 1.0
        geom.append({
            "i": led["i"],
            "cx": led["x"] * SC + (SPLIT_GAP if led["i"] >= split[0] else 0),
            "cy": led["y"] * SC,
            "w": KEY_W,
            "h": KEY_H * tall,
            "half": 0 if led["i"] < split[0] else 1,
            "matrix": list(led["matrix"]),
        })

    x0 = min(g["cx"] - g["w"] / 2 for g in geom) - MARGIN
    x1 = max(g["cx"] + g["w"] / 2 for g in geom) + MARGIN
    y0 = min(g["cy"] - g["h"] / 2 for g in geom) - MARGIN
    y1 = max(g["cy"] + g["h"] / 2 for g in geom) + MARGIN
    for g in geom:
        g["cx"] -= x0
        g["cy"] -= y0
    return geom, int(round(x1 - x0)), int(round(y1 - y0))


# --------------------------------------------------------------------------
# 逐帧渲染
# --------------------------------------------------------------------------


def box_of(g, cx_off=0.0, cy_off=0.0, shrink=0.0):
    w = g["w"] - shrink
    h = g["h"] - shrink
    cx = g["cx"] + cx_off
    cy = g["cy"] + cy_off
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def render_frame(frame, geom, W, H):
    """一帧：暗色键帽 + 模糊光晕 + 清晰的灯。"""
    base = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(base)
    for g in geom:
        d.rounded_rectangle(box_of(g), radius=8, fill=CAP, outline=CAP_EDGE, width=1)

    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    sharp = Image.new("RGB", (W, H), (0, 0, 0))
    sd = ImageDraw.Draw(sharp)
    for g, rgb in zip(geom, frame):
        col = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        gd.rounded_rectangle(box_of(g), radius=8, fill=col)
        sd.rounded_rectangle(box_of(g, shrink=6), radius=6, fill=col)

    img = ImageChops.add(base, glow.filter(ImageFilter.GaussianBlur(10)))
    return ImageChops.add(img, sharp)


def global_palette(imgs, colors):
    """整段动画共用一张调色板。

    每帧各自 ADAPTIVE 量化的话，同一颗灯在不同帧会被映到调色板里不同的位置，
    GIF 的 LZW 就压不动了（实测一个 6.7 MB，共用调色板只要 0.2 MB）。
    所以先拿十几帧拼成一张大图求一次调色板，再让所有帧都往它上面映射。
    这么多帧的颜色本来就只有「键帽灰 + 若干灯色 + 各自的光晕」，32 色足够。
    """
    step = max(1, len(imgs) // 12)
    picks = imgs[::step][:12]
    w, h = picks[0].size
    cols = 4
    rows = (len(picks) + cols - 1) // cols
    montage = Image.new("RGB", (w * cols, h * rows), BG)
    for i, im in enumerate(picks):
        montage.paste(im, ((i % cols) * w, (i // cols) * h))
    return montage.convert("P", palette=Image.ADAPTIVE, colors=colors, dither=Image.NONE)


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------


def cie_curve():
    """从 QMK 源码里抠出 CIE1931 亮度曲线表（256 项）。

    这份固件编译时带 `-DUSE_CIE1931_CURVE`（见 `.build/obj_sofle_pico_default/cflags.txt`），
    `hsv_to_rgb()` 会先把 hsv.v 过一遍这张表，所以亮度不是线性的：
    v=127（亮度上限）实际只有 47 级。网页播放器要用同一张表，滑块才是固件的真实亮度。
    """
    body = open(LED_TABLES_C, encoding="utf-8").read()
    body = body.split("CIE1931_CURVE[256] PROGMEM = {", 1)[1].split("};", 1)[0]
    vals = [int(v) for v in re.findall(r"\d+", body)]
    if len(vals) != 256:
        sys.exit(f"CIE1931_CURVE 解析出 {len(vals)} 项，应该是 256 项")
    return vals


def match_effects(data):
    """把采集器里的灯效按 EFFECTS 的顺序排好；缺的/多出来的都报出来。"""
    got = {}
    for eff in data["effects"]:
        norm = eff["name"].lower().replace("-", "_")
        for canon, keys in ALIASES.items():
            if any(k in norm for k in keys):
                got[canon] = eff
                break
    missing = [c for c, _, _, _ in EFFECTS if c not in got and c != WHITE_ID]
    extra = [e["name"] for e in data["effects"] if e["name"] not in
             {v["name"] for v in got.values()}]
    return got, missing, extra


def synthetic_white(n_led, frames=1):
    """纯白常亮的帧：不是从采集器里来的，而是照固件那条路径算出来的常量。

    `solid_color` 就是 `rgb_matrix_set_color(i, hsv_to_rgb(rgb_matrix_config.hsv))`，
    而 sat=0 时 `hsv_to_rgb()` 直接走 `rgb.r = rgb.g = rgb.b = CIE1931_CURVE[hsv.v]`
    这个分支——所以 58 颗灯全是 `CIE1931_CURVE[127] = 47`（默认亮度上限 127）。
    这个灯效本来就是静态的，没有逐帧变化，所以一帧就够。
    """
    c = cie_curve()[127]
    frame = [[c, c, c] for _ in range(n_led)]
    return {"name": WHITE_ID, "mode": 1, "frames": [frame] * frames}


def main():
    scale = 0.6
    stride = 2       # GIF 每 2 帧取 1 帧（网页播放器仍然用全部帧）
    colors = 32      # 整段 GIF 共用的调色板大小
    for flag, cast in (("--scale", float), ("--stride", int), ("--colors", int)):
        if flag in sys.argv:
            val = cast(sys.argv[sys.argv.index(flag) + 1])
            if flag == "--scale":
                scale = val
            elif flag == "--stride":
                stride = max(1, val)
            else:
                colors = max(2, val)

    frames_json = FRAMES_JSON
    if "--frames-json" in sys.argv:
        frames_json = sys.argv[sys.argv.index("--frames-json") + 1]

    if not os.path.exists(frames_json):
        sys.exit(f"找不到 {frames_json}，先在 led_effects/ 里跑 bash build.sh")
    data = json.load(open(frames_json))

    leds, keys, split, rgb = load_keyboard()
    geom, W, H = build_geometry(leds, keys, split)
    n_led = len(geom)
    if data["led_count"] != n_led:
        sys.exit(f"采集器给了 {data['led_count']} 颗灯，keyboard.json 里是 {n_led} 颗")

    got, missing, extra = match_effects(data)
    got[WHITE_ID] = synthetic_white(n_led)   # 纯白常亮：常量，不进采集器
    if missing:
        print("⚠ 采集器里没有这些灯效：", ", ".join(missing))
    if extra:
        print("ℹ 采集器里多出来的灯效（本页不展示）：", ", ".join(extra))

    dt_ms = int(data.get("dt_ms", 68))
    fps = round(1000.0 / dt_ms, 1)

    js_effects = []
    for canon, keycode, title, desc in EFFECTS:
        eff = got.get(canon)
        if eff is None:
            continue
        frames = eff["frames"]
        for fi, fr in enumerate(frames):
            if len(fr) != n_led:
                sys.exit(f"{eff['name']} 第 {fi} 帧有 {len(fr)} 颗灯，应该是 {n_led}")

        imgs = [render_frame(fr, geom, W, H) for fr in frames]
        if scale != 1.0:
            size = (int(W * scale), int(H * scale))
            imgs = [im.resize(size, Image.LANCZOS) for im in imgs]
        # GIF：抽帧 + 整段共用一张调色板（体积能差 20 倍以上）
        picks = imgs[::stride]
        pal = global_palette(picks, colors)
        picks = [im.quantize(palette=pal, dither=Image.NONE) for im in picks]
        gif = os.path.join(OUT_DIR, f"fx_{canon}.gif")
        picks[0].save(gif, save_all=True, append_images=picks[1:], duration=dt_ms * stride,
                      loop=0, optimize=True)

        raw = bytearray()
        for fr in frames:
            for px in fr:
                raw += bytes((int(px[0]) & 0xFF, int(px[1]) & 0xFF, int(px[2]) & 0xFF))
        js_effects.append({
            "id": canon,
            "key": keycode,
            "title": title,
            "desc": desc,
            "frames": len(frames),
            "data": base64.b64encode(bytes(raw)).decode("ascii"),
        })
        peak = max((max(px) for fr in frames for px in fr), default=0)
        moving = sum(1 for fr in frames[1:] if fr != frames[0])
        print(f"  fx_{canon}.gif  {len(picks)} 帧 / {round(1000.0 / (dt_ms * stride), 1)} fps · "
              f"{picks[0].size[0]}x{picks[0].size[1]} · 峰值 {peak:3d} · "
              f"与首帧不同的帧 {moving}/{len(frames) - 1} · "
              f"{os.path.getsize(gif) / 1024:.0f} KB")

    payload = {
        "led_count": n_led,
        "canvas": [W, H],
        "fps": fps,
        "dt_ms": dt_ms,
        "max_brightness": data.get("max_brightness", 127),
        "cie": cie_curve(),
        "split": split,
        "hsv": data.get("hsv"),
        "speed": data.get("speed"),
        "leds": geom,
        "effects": js_effects,
    }
    with open(JS_OUT, "w") as fh:
        fh.write("// 由 gen_led_effects.py 生成，数据来自 led_effects/led_frames.json（真机灯效源码逐帧重放）\n")
        fh.write("window.SOFLE_LED_FX = ")
        json.dump(payload, fh, separators=(",", ":"))
        fh.write(";\n")
    print(f"已生成: {JS_OUT}（{os.path.getsize(JS_OUT) / 1024:.0f} KB）")
    frame_counts = sorted({e["frames"] for e in js_effects})
    span = (f"{frame_counts[0]}~{frame_counts[-1]} 帧" if len(frame_counts) > 1
            else f"{frame_counts[0] if frame_counts else 0} 帧")
    print(f"画布 {W}x{H}，{n_led} 颗灯，{len(js_effects)} 个灯效 × {span} / {fps} fps"
          f"（纯白是静态的，只有 1 帧）")


if __name__ == "__main__":
    main()
