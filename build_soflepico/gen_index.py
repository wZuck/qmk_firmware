#!/usr/bin/env python3
"""生成 index.html：把固件信息、键位图、OLED 三种画面汇成一页，方便浏览/分享。

图片都是相对路径引用（keymap_layers.png、oled_preview/**），所以打开本机的
index.html 就能看，不需要起服务器。

用法： python3 gen_index.py
"""

import hashlib
import html
import importlib.util
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True  # 不要在 oled_preview/ 里留 __pycache__

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UF2 = os.path.join(HERE, "sofle_pico_default.uf2")
OUT = os.path.join(HERE, "index.html")


def git(*args):
    try:
        return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "?"


def file_info(path):
    if not os.path.exists(path):
        return "?", "?"
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return h, time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))


def preview_module():
    spec = importlib.util.spec_from_file_location(
        "gen_oled_preview", os.path.join(HERE, "oled_preview", "gen_oled_preview.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def led_effects_module():
    """同目录的灯效脚本：借它手里的 EFFECTS 清单（名字/键码/说明）保持一处定义。"""
    spec = importlib.util.spec_from_file_location(
        "gen_led_effects", os.path.join(HERE, "gen_led_effects.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def card(src, title, note="", link=None, wide=False):
    link = link or src
    return f"""      <figure class="card{' wide' if wide else ''}">
        <a href="{html.escape(link)}"><img src="{html.escape(src)}" alt="{html.escape(title)}" loading="lazy"></a>
        <figcaption><b>{html.escape(title)}</b>{('<br><span class="dim">' + html.escape(note) + '</span>') if note else ''}</figcaption>
      </figure>"""


def main():
    preview = preview_module()
    ledfx = led_effects_module()
    sha, built = file_info(UF2)
    size = os.path.getsize(UF2) if os.path.exists(UF2) else 0
    commit = git("rev-parse", "--short", "HEAD")
    commit_date = git("log", "-1", "--format=%cd", "--date=short")
    tag = git("describe", "--tags")

    # 灯效：GIF 由 gen_led_effects.py 从「跑真实灯效源码」的逐帧数据画出来
    fx_files = {cid: f"led_effects/fx_{cid}.gif" for cid, _, _, _ in ledfx.EFFECTS}
    fx_cards = "\n".join(
        card(fx_files[cid], f"{title}（GIF）", f"{keycode} · {desc}",
             link=fx_files[cid])
        for cid, keycode, title, desc in ledfx.EFFECTS
        if os.path.exists(os.path.join(HERE, fx_files[cid]))
    )
    fx_missing = [cid for cid in fx_files if not os.path.exists(os.path.join(HERE, fx_files[cid]))]

    info_screens = ([(n, d) for n, d, _ in preview.LEFT_STATES]
                    + [(n, d) for n, d, _ in preview.STATS_STATES]
                    + [(n, d) for n, d, _ in preview.GRAPH_STATES]
                    + [(n, d) for n, d, _ in preview.LAYER_STATES])
    status_cards = "\n".join(
        card(f"oled_preview/4x/{name}.png", desc, link=f"oled_preview/1x/{name}.png")
        for name, desc in info_screens
    )
    anims = preview.parse_anims(os.path.join(preview.KM_DIR, "oled_anim.h"))
    anims_inv = preview.parse_anims(os.path.join(preview.KM_DIR, "oled_anim_inv.h"), "oled_anim_inv")
    anim_titles = dict(preview.parse_anim_titles(os.path.join(preview.KM_DIR, "oled_anim.h")))

    def anim_section(idx, name, frames):
        gif = card(f"oled_preview/anim_{name}.gif", f"{name} 循环（GIF）", "8 帧 / 8 fps",
                   link=f"oled_preview/anim_{name}.gif")
        strip = "\n".join(
            card(f"oled_preview/4x/anim_{name}_{i:02d}.png", f"帧 {i + 1}",
                 link=f"oled_preview/1x/anim_{name}_{i:02d}.png")
            for i in range(len(frames))
        )
        return (f'  <h4>anim {idx}/{len(anims)} · {name} <span class="dim">— '
                f'{html.escape(anim_titles.get(name, ""))}</span></h4>\n  <div class="grid">\n'
                + gif + "\n" + strip + "\n  </div>")

    anim_sections = "\n".join(anim_section(i + 1, n, f) for i, (n, f) in enumerate(anims))

    # 反色（白天）版：同一批 loop，每个像素翻过来
    def anim_inv_section(idx, name, frames):
        gif = card(f"oled_preview/anim_inv_{name}.gif", f"{name} 反色（GIF）", "8 帧 / 8 fps",
                   link=f"oled_preview/anim_inv_{name}.gif")
        strip = "\n".join(
            card(f"oled_preview/4x/anim_inv_{name}_{i:02d}.png", f"帧 {i + 1}",
                 link=f"oled_preview/1x/anim_inv_{name}_{i:02d}.png")
            for i in range(len(frames))
        )
        return (f'  <h4>anim inv {idx}/{len(anims_inv)} · {name} 反色 <span class="dim">— '
                f'{html.escape(anim_titles.get(name, ""))}，每个像素翻转（白天模式）</span></h4>\n  <div class="grid">\n'
                + gif + "\n" + strip + "\n  </div>")

    anim_inv_sections = "\n".join(anim_inv_section(i + 1, n, f) for i, (n, f) in enumerate(anims_inv))

    # 雪人（oled_snow.h）：OLED 键循环里的 snow 画面，排在四组反色动画之后
    snow_frames = preview.parse_snow(os.path.join(preview.KM_DIR, "oled_snow.h"))
    snow_section = ""
    if snow_frames:
        snow_gif = card("oled_preview/snow_pair.gif", "雪人两帧循环（GIF）", "2 帧",
                        link="oled_preview/snow_pair.gif")
        snow_inv_frames = preview.parse_snow(os.path.join(preview.KM_DIR, "oled_snow.h"), "oled_snow_inv")
        snow_strip = "\n".join(
            card(f"oled_preview/4x/snow_{i:02d}.png", f"帧 {i + 1}（正色）",
                 link=f"oled_preview/1x/snow_{i:02d}.png")
            for i in range(len(snow_frames))
        ) + "\n" + card("oled_preview/snow_pair_inv.gif", "雪人反色两帧循环（GIF）", "2 帧 · 白天模式",
                         link="oled_preview/snow_pair_inv.gif") + "\n" + "\n".join(
            card(f"oled_preview/4x/snow_inv_{i:02d}.png", f"帧 {i + 1}（反色）",
                 link=f"oled_preview/1x/snow_inv_{i:02d}.png")
            for i in range(len(snow_inv_frames))
        ) + "\n" + card("oled_preview/snow_polarities.png", "正色 / 反色对照",
                         "左二正色、右二反色", link="oled_preview/snow_polarities.png")
        snow_section = (
            f'  <h4>雪人 · snow_pair <span class="dim">— '
            f'oled_snow.h（oled_snow1/2.pdf 抽出的 {len(snow_frames)} 帧）；'
            f'OLED 键循环里的 snow 画面（四组反色动画之后）</span></h4>\n  <div class="grid">\n'
            + snow_gif + "\n" + snow_strip + "\n  </div>")

    card_mascot_polarities = card(
        "oled_preview/mascot_polarities.png", "小怪物：上行正色 / 下行反色",
        "四组动画各取第 1 帧", link="oled_preview/mascot_polarities.png",
    )

    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>sofle_pico default 固件 · 键位图与 OLED 预览</title>
<style>
  :root {{ --ink:#1f2933; --dim:#66727f; --line:#dde3ea; --bg:#f4f6f9; --card:#fff; --oled:#0a0e12; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font:16px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:36px 24px 72px; }}
  h1 {{ font-size:30px; margin:0 0 6px; }}
  h2 {{ font-size:21px; margin:44px 0 14px; padding-bottom:8px; border-bottom:2px solid var(--line); }}
  h3 {{ font-size:17px; margin:26px 0 10px; color:#33414f; }}
  p.lead {{ color:var(--dim); margin:0 0 26px; }}
  .panel {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; }}
  table {{ border-collapse:collapse; width:100%; font-size:14.5px; }}
  th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ color:var(--dim); font-weight:600; white-space:nowrap; }}
  code {{ background:#eef1f5; padding:1px 5px; border-radius:5px; font-size:13.5px; }}
  .hash {{ font-family:ui-monospace,Menlo,Monaco,monospace; font-size:12.5px; word-break:break-all; }}
  .grid {{ display:grid; gap:18px; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); }}
  .card {{ margin:0; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:10px; }}
  .card img {{ display:block; width:100%; image-rendering:pixelated; border-radius:8px; background:var(--oled); }}
  .card figcaption {{ font-size:13px; margin-top:8px; line-height:1.45; }}
  .dim {{ color:var(--dim); }}
  .wide {{ grid-column:1/-1; }}
  .wide img {{ max-width:900px; background:#fff; }}
  .gif {{ max-width:230px; }}
  a {{ color:#1a56b8; }}
  ul {{ padding-left:22px; }}
  .cols {{ display:grid; gap:18px; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }}
  .fx-player {{ padding:14px; }}
  .fx-bar {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }}
  .fx-btn {{ font:inherit; font-size:13.5px; padding:6px 12px; border:1px solid var(--line);
             background:var(--card); color:var(--ink); border-radius:999px; cursor:pointer; }}
  .fx-btn:hover {{ border-color:#9aa5b1; }}
  .fx-btn.on {{ background:#1a56b8; border-color:#1a56b8; color:#fff; }}
  .fx-canvas {{ display:block; width:100%; height:auto; border-radius:10px; background:var(--oled); }}
  .fx-caption {{ font-size:13.5px; color:var(--dim); margin:10px 0 0; }}
  .fx-sliders {{ display:flex; flex-wrap:wrap; gap:14px 18px; align-items:center; margin-top:12px; }}
  .fx-slider {{ display:flex; align-items:center; gap:8px; font-size:13.5px; color:var(--dim); }}
  .fx-slider input {{ width:128px; }}
  .fx-slider b {{ color:var(--ink); font-variant-numeric:tabular-nums; min-width:56px; }}
  .fx-play {{ margin-left:auto; }}
  footer {{ margin-top:54px; color:var(--dim); font-size:13.5px; }}
</style>
</head>
<body>
<div class="wrap">

  <h1>sofle_pico <code>default</code> 固件</h1>
  <p class="lead">键位图、OLED 显示内容预览、烧录说明。图片都是按固件里的绘图代码逐字节重放出来的，不是照片。</p>

  <div class="panel">
    <table>
      <tr><th>键盘 / keymap</th><td><code>sofle_pico</code> / <code>default</code>（RP2040，分体，左右各一个 EC11）</td></tr>
      <tr><th>固件</th><td><code>sofle_pico_default.uf2</code> · {size:,} 字节 · 构建于 {built}</td></tr>
      <tr><th>SHA-256</th><td class="hash">{sha}</td></tr>
      <tr><th>QMK</th><td>tag <code>{tag}</code> · commit <code>{commit}</code>（{commit_date}）</td></tr>
      <tr><th>硬件排查</th><td><code>matrix_map_left.svg</code>（左手矩阵图）· <code>pico_pinout.svg</code>（Pico 引脚图）· <code>hardware_check.md</code>（排查流程）</td></tr>
      <tr><th>键位图</th><td><code>keymap_layers.svg</code>（矢量）· <code>keymap_layers.png</code>（2 倍光栅）</td></tr>
      <tr><th>灯光</th><td><code>led_map.svg</code>（矢量）· <code>led_map.png</code>（2 倍光栅）——58 颗逐键 RGB 的索引、矩阵位置和灯带走向；ADJUST 层上有开关/切换/色相/饱和/亮度/速度键和 9 个灯效直达键（含默认的纯白常亮，见下面「LED 灯效」）</td></tr>
      <tr><th>编译命令</th><td><code>qmk compile -kb sofle_pico -km default</code></td></tr>
      <tr><th>层</th><td>QWERTY(0) / LOWER(1) / RAISE(2) / ADJUST(3)，<code>LOWER</code>+<code>RAISE</code> 三键组合出 ADJUST</td></tr>
      <tr><th>旋钮</th><td>左：音量 ± / 按压静音　右：上一首·下一首 / 按压播放暂停</td></tr>
      <tr><th>VIA 测试器</th><td>固件里开了 <code>VIA_INSECURE</code>，VIA 网页版的 Key Tester 才能读到实时按键（代价：raw HID 可被读键盘，见 README）</td></tr>
      <tr><th>ADJUST 层</th><td>灯光键（开关 / 切换 / 色相 / 饱和 / 亮度 / 速度 + 9 个灯效直达，第一个是纯白常亮）· <code>OLED</code>（左右各一个，切换本侧画面）· <code>EE_CLR</code>（清 EEPROM）· <code>Mac/Win</code> · <code>Boot</code> · 媒体键；这一层两个旋钮临时改成调灯（左=亮度、右=速度）</td></tr>
    </table>
  </div>

  <h2>键位图（四层）</h2>
  <div class="grid">
{card("matrix_map_left.svg", "左手矩阵排查图", "每个键标出物理键位和 rXcY，绿色=实测能出、红色=实测不出；边框颜色=所属列。配 pico_pinout.svg 一起看", wide=True)}
{card("pico_pinout.svg", "Pico 引脚对照", "40 脚里矩阵行/列、RGB、OLED、旋钮、TRRS 各是哪些，测引脚时对着找", wide=True)}
{card("keymap_layers.svg", "四层键位图（矢量）", "矢量版放多大都不糊；PNG 版：keymap_layers.png（2 倍，1468x3300）；文字版见 keymap.md", wide=True)}
{card("led_map.svg", "逐键 RGB 灯位图", "58 颗 WS2812 逐键灯的全局索引、本半灯带序号、矩阵位置和灯带走向；左右各一条独立灯带，数据脚 GP0", wide=True)}
  </div>

  <h2>LED 灯效（逐键 RGB · 左右各 29 颗）</h2>
  <p class="lead">出厂默认是<b>纯白常亮</b>（<code>solid_color</code> + 饱和 0，58 颗灯一起白），
     下面是它和另外 8 种灯效。这些动画都是<b>把固件里的灯效代码拿到电脑上逐帧重放</b>出来的，不是照着效果图临摹：
     <code>led_effects/harness.c</code> 直接编译 <code>quantum/rgb_matrix/animations/</code> 里的真实源码，
     用真的 <code>g_led_config</code> 坐标和真的 <code>hsv_to_rgb()</code> 跑 120 帧，再画成 GIF / 网页动画。
     按键涟漪和打字热图那两种，画面里的“打字”是按固定节奏注入的按键事件（约 59 WPM）打出来的。</p>

  <div id="ledfx" class="panel fx-player">
    <noscript><p>这块要开 JavaScript 才能点；下面的 GIF 不开 JS 也能看。</p></noscript>
  </div>

  <h3>ADJUST 层上的灯光键（左右各一组）</h3>
  <div class="panel">
    <table>
      <tr><th>开 / 关</th><td><code>RM_TOGG</code>　（ADJUST 层左旋钮<b>按下</b>也是它）</td></tr>
      <tr><th>换灯效</th><td><code>RM_NEXT</code> / <code>RM_PREV</code> 在 41 种里前后翻　（右旋钮<b>按下</b> = 下一个）</td></tr>
      <tr><th>亮度</th><td><code>RM_VALU</code> / <code>RM_VALD</code>　或 ADJUST 层<b>左旋钮</b>（同层的音量键不受影响）</td></tr>
      <tr><th>色相 / 饱和</th><td><code>RM_HUEU</code> / <code>RM_HUED</code>、<code>RM_SATU</code> / <code>RM_SATD</code></td></tr>
      <tr><th>速度</th><td><code>RM_SPDU</code> / <code>RM_SPDD</code>　或 ADJUST 层<b>右旋钮</b></td></tr>
      <tr><th>纯白常亮</th><td><code>FX_WHITE</code>（ADJUST 层下排最左，出厂默认灯效）——饱和度归零 + 切到 <code>solid_color</code>，亮度也回到出厂值（127），相当于「恢复出厂灯效」</td></tr>
      <tr><th>直达 9 种</th><td>ADJUST 层 row3 最左边 4~5 列（左 5 右 4）：<code>FX_WHITE</code> · <code>FX_CYCLE_OUT_IN</code> · <code>FX_HUE_WAVE</code> ·
          <code>FX_RAINBOW_BEACON</code> · <code>FX_PIXEL_FLOW</code> · <code>FX_JELLYBEAN</code> ·
          <code>FX_DIGITAL_RAIN</code> · <code>FX_REACTIVE_NEXUS</code> · <code>FX_TYPING_HEATMAP</code></td></tr>
      <tr><th>其它层</th><td>这几个键只写在 ADJUST 层，别的层上旋钮照旧是音量 / 切歌；直达键只改 RAM，重启回到 EEPROM 里的设置</td></tr>
      <tr><th>EEPROM</th><td>键位表变了（<code>SOFLE_EEPROM_VERSION</code> 现在是 4），烧完第一次启动会顺手把键位和<b>灯光设置</b>都刷回固件默认——也就是纯白常亮；之后在 VIA / 键盘上改的灯效会一直留着</td></tr>
    </table>
  </div>

  <h3>每个灯效一段 GIF</h3>
  <div class="grid">
{fx_cards}
  </div>

  <h2>OLED 画面</h2>
  <p class="lead">每一半都能用自己那侧的 <code>OLED</code> 键循环切换：
     status → stats → graph → layers → 4 组小怪物动画（正色）→ 4 组反色 → 雪人（正色）→ 雪人（反色）。
     按住不放会自动往下翻（每 400 ms 一张），
     不用点十几次。默认左边 status、右边第一组动画；选择只存 RAM，重启回到默认。
     开机时两半都会先播 ~1.8 秒动画。</p>

  <h3>① 信息屏（默认：左手显示 status）</h3>
  <p class="lead">四类共 13 个画面：<b>status</b> 状态屏（层名 / Mac-Win / 实时修饰键 / 峰值 / WPM 进度条 / Caps）、
     <b>stats</b> 统计（按键数 / WPM / 峰值 / 当前层 / 运行时间）、
     <b>graph</b> WPM 曲线（大号数字 + 最近 21 秒柱状图）、
     <b>layers</b> 层状态（四个层的开关，能看出三键组合出 ADJUST）。</p>
  <div class="grid">
{status_cards}
  </div>

  <h3>② anim 动画（默认：右手第一组）</h3>
  <p class="lead">四组大眼小怪物的 8 帧循环（8 fps）：bounce / wave / walk / sleep。
     每组都有 GIF，下面按组列出全部帧。</p>
{anim_sections}

  <h3>③ 雪人那组（另一套动画图）</h3>
  <p class="lead">从 <code>oled_snow1.pdf</code> / <code>oled_snow2.pdf</code> 里抽出来的两个滑雪小人，
     缩到 64 px 宽后就是 <code>oled_snow.h</code> 的两帧。右半的动画屏由 ADJUST 层的
     就是<b>原来那个 <code>OLED</code> 键</b>循环里的画面——四组小怪物动画之后，正色一屏、反色一屏，
     不用另按别的键。</p>
{snow_section}


  <h2>烧录</h2>
  <div class="cols">
    <div class="panel">
      <h3 style="margin-top:0">进 bootloader</h3>
      <p>按住 Pico 的 <code>BOOT</code> → 点一下 <code>RST</code> → 先松 <code>RST</code> 再松 <code>BOOT</code>，
         会出现名为 <code>RPI-RP2</code> 的 U 盘。</p>
      <p>把 <code>sofle_pico_default.uf2</code> 拖进去即可。或用命令：</p>
      <p><b>两个半边各烧各的</b>（<code>EE_HANDS</code> 的手性存在 EEPROM 里）：</p>
      <ul>
        <li><code>sofle_pico_default_split-left.uf2</code> → 左手（启动时强制手性=左）</li>
        <li><code>sofle_pico_default_split-right.uf2</code> → 右手（启动时强制手性=右）</li>
        <li><code>sofle_pico_default.uf2</code> → 任意半边，不动手性（确定本来是对的才用）</li>
      </ul>
      <p><code>qmk flash -kb sofle_pico -km default -bl uf2-split-left</code>（右半换成 <code>-right</code>）</p>
    </div>
    <div class="panel">
      <h3 style="margin-top:0">EEPROM 里的键位会自动跟着更新</h3>
      <p>固件启用了 VIA，键位是<b>从 EEPROM 读</b>的，<code>keymap.c</code> 只在 EEPROM 首次初始化时写进去。
         所以固件里放了一个 <code>SOFLE_EEPROM_VERSION</code>：启动时发现 EEPROM 的版本对不上，
         就自动用固件里的键位重写一遍。改了层结构只要把这个常量 +1，烧完启动就生效。</p>
      <p>手动兜底仍然在：<code>ADJUST</code> 层的 <code>EE_CLR</code>（左手 <code>T</code> 键位置）或 VIA 的 Reset Keymap。</p>
      <p class="dim">另外：两个旋钮若拧反了，把 <code>encoder_map</code> 里那一对键码对调即可。</p>
    </div>
  </div>

  <h2>相关文件</h2>
  <ul>
    <li><a href="README.md">README.md</a> —— 构建信息、功能要点、验证记录、注意事项</li>
    <li><a href="keymap.md">keymap.md</a> —— 四层键位表、换层方式、旋钮、自定义键</li>
    <li><a href="oled_preview/README.md">oled_preview/README.md</a> —— OLED 三种画面、切换机制、换图方法</li>
    <li><a href="sofle_pico_default.uf2">sofle_pico_default.uf2</a> · <a href="sofle_pico_default.hex">.hex</a> · <a href="sofle_pico_default.elf">.elf</a> · <a href="sofle_pico_default.map">.map</a></li>
    <li><code>gen_index.py</code> / <code>gen_keymap_image.py</code> / <code>gen_matrix_image.py</code> / <code>gen_pico_pinout.py</code> / <code>gen_led_map.py</code> / <code>oled_preview/gen_oled_preview.py</code> —— 本页图片的生成脚本</li>
    <li><a href="verify_keymap.py">verify_keymap.py</a> —— 从编译好的 ELF 里读回 <code>keymaps</code> / <code>encoder_map</code> 并按层打印键码名字（改完 keymap.c 用它确认真的编进去了）</li>
    <li><a href="led_effects/README.md">led_effects/README.md</a> · <a href="led_effects/harness.c">harness.c</a> —— 灯效逐帧采集器：在电脑上编译真实的 QMK 灯效源码，导出每一帧的 58 颗灯颜色</li>
    <li><code>gen_led_effects.py</code> · <code>led_effects.js</code> · <code>led_player.js</code> —— 把逐帧数据画成 GIF，并给本页的互动播放器用</li>
  </ul>

  <footer>本页由 <code>gen_index.py</code> 生成 · 固件 SHA-256 <span class="hash">{sha[:16]}…</span></footer>
</div>

<script src="led_effects.js"></script>
<script src="led_player.js"></script>
</body>
</html>
"""
    with open(OUT, "w") as fh:
        fh.write(doc)
    print("已生成:", OUT)
    print(f"固件 {size} 字节, sha256 {sha[:16]}…, QMK {tag} @ {commit}")
    print(f"图片: 键位图 1 + 信息屏 {len(info_screens)} + anim {sum(len(f) for _, f in anims)}"
          f" + anim反色 {sum(len(f) for _, f in anims_inv)} + 雪人 {len(snow_frames) * 2}")
    print(f"灯效: {len(fx_files) - len(fx_missing)} 个 GIF"
          + (f"（缺 {'、'.join(fx_missing)}：先跑 led_effects/ 里的采集器再跑 gen_led_effects.py）"
             if fx_missing else "")
          + f" · 互动播放器数据{'已就绪' if os.path.exists(os.path.join(HERE, 'led_effects.js')) else '缺失（跑 gen_led_effects.py）'}")


if __name__ == "__main__":
    main()
