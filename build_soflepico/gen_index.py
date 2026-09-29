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


def card(src, title, note="", link=None, wide=False):
    link = link or src
    return f"""      <figure class="card{' wide' if wide else ''}">
        <a href="{html.escape(link)}"><img src="{html.escape(src)}" alt="{html.escape(title)}" loading="lazy"></a>
        <figcaption><b>{html.escape(title)}</b>{('<br><span class="dim">' + html.escape(note) + '</span>') if note else ''}</figcaption>
      </figure>"""


def main():
    preview = preview_module()
    sha, built = file_info(UF2)
    size = os.path.getsize(UF2) if os.path.exists(UF2) else 0
    commit = git("rev-parse", "--short", "HEAD")
    commit_date = git("log", "-1", "--format=%cd", "--date=short")
    tag = git("describe", "--tags")

    status_cards = "\n".join(
        card(f"oled_preview/4x/{name}.png", desc, link=f"oled_preview/1x/{name}.png")
        for name, desc, _ in preview.LEFT_STATES
    )
    anim_cards = "\n".join(
        card(f"oled_preview/4x/anim_{i:02d}.png", f"帧 {i + 1}", link=f"oled_preview/1x/anim_{i:02d}.png")
        for i in range(len(preview.parse_anim(os.path.join(preview.KM_DIR, "oled_anim.h"))))
    )
    logo_card = card(
        "oled_preview/4x/screen_logo.png", "logo",
        "oled_image.h（64x96 静态图）", link="oled_preview/1x/screen_logo.png",
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
      <tr><th>编译命令</th><td><code>qmk compile -kb sofle_pico -km default</code></td></tr>
      <tr><th>层</th><td>QWERTY(0) / LOWER(1) / RAISE(2) / ADJUST(3)，<code>LOWER</code>+<code>RAISE</code> 三键组合出 ADJUST</td></tr>
      <tr><th>旋钮</th><td>左：音量 ± / 按压静音　右：上一首·下一首 / 按压播放暂停</td></tr>
      <tr><th>ADJUST 层</th><td><code>OLED</code>（左右各一个，切换本侧画面）· <code>EE_CLR</code>（清 EEPROM）· <code>Mac/Win</code> · <code>Boot</code> · 媒体键</td></tr>
    </table>
  </div>

  <h2>键位图（四层）</h2>
  <div class="grid">
{card("keymap_layers.png", "四层键位图", "点图看原图；文字版说明见 keymap.md", wide=True)}
  </div>

  <h2>OLED 画面</h2>
  <p class="lead">每一半都能用自己那侧的 <code>OLED</code> 键在三种画面之间循环：status → anim → logo。
     默认左边 status、右边 anim；选择只存 RAM，重启回到默认。开机时两半都会先播 ~1.8 秒动画。</p>

  <h3>① status 状态屏（默认：左手）</h3>
  <p class="lead">层名大字 / Mac-Win / 实时修饰键（C S A G，未按住显示 <code>.</code>）/ 本轮打字峰值 WPM / 当前 WPM 与进度条 / Caps Lock。</p>
  <div class="grid">
{status_cards}
  </div>

  <h3>② anim 动画（默认：右手）</h3>
  <p class="lead">大眼小怪物：弹跳 + 落地压扁 + 眨眼 + 摆手 + 眼珠转动，8 帧、8 fps。
     <a href="oled_preview/anim.gif">打开 GIF</a> 看动态效果。</p>
  <div class="grid">
{card("oled_preview/anim.gif", "动画循环（GIF）", "8 帧 / 8 fps", link="oled_preview/anim.gif")}
{anim_cards}
  </div>

  <h3>③ logo 静态图</h3>
  <div class="grid">
{logo_card}
  </div>

  <h2>烧录</h2>
  <div class="cols">
    <div class="panel">
      <h3 style="margin-top:0">进 bootloader</h3>
      <p>按住 Pico 的 <code>BOOT</code> → 点一下 <code>RST</code> → 先松 <code>RST</code> 再松 <code>BOOT</code>，
         会出现名为 <code>RPI-RP2</code> 的 U 盘。</p>
      <p>把 <code>sofle_pico_default.uf2</code> 拖进去即可。或用命令：</p>
      <p><code>qmk flash -kb sofle_pico -km default -bl uf2-split-left</code><br>
         <code>qmk flash -kb sofle_pico -km default -bl uf2-split-right</code></p>
      <p class="dim">两半都要烧同一份固件；手性靠 EEPROM（<code>EE_HANDS</code>）。</p>
    </div>
    <div class="panel">
      <h3 style="margin-top:0">烧完先清一次 EEPROM</h3>
      <p>固件启用了 VIA，键位是<b>从 EEPROM 读</b>的，<code>keymap.c</code> 只在 EEPROM 首次初始化时写进去。
         改了键位（删层、加 <code>OLED</code> 键）之后，必须清一次才会生效：</p>
      <ul>
        <li>在 <code>ADJUST</code> 层按一下 <code>EE_CLR</code>（左手 <code>T</code> 键位置），或</li>
        <li>用 VIA 的 Reset Keymap。</li>
      </ul>
      <p class="dim">另外：两个旋钮若拧反了，把 <code>encoder_map</code> 里那一对键码对调即可。</p>
    </div>
  </div>

  <h2>相关文件</h2>
  <ul>
    <li><a href="README.md">README.md</a> —— 构建信息、功能要点、验证记录、注意事项</li>
    <li><a href="keymap.md">keymap.md</a> —— 四层键位表、换层方式、旋钮、自定义键</li>
    <li><a href="oled_preview/README.md">oled_preview/README.md</a> —— OLED 三种画面、切换机制、换图方法</li>
    <li><a href="sofle_pico_default.uf2">sofle_pico_default.uf2</a> · <a href="sofle_pico_default.hex">.hex</a> · <a href="sofle_pico_default.elf">.elf</a> · <a href="sofle_pico_default.map">.map</a></li>
    <li><code>gen_index.py</code> / <code>gen_keymap_image.py</code> / <code>oled_preview/gen_oled_preview.py</code> —— 本页图片的生成脚本</li>
  </ul>

  <footer>本页由 <code>gen_index.py</code> 生成 · 固件 SHA-256 <span class="hash">{sha[:16]}…</span></footer>
</div>
</body>
</html>
"""
    with open(OUT, "w") as fh:
        fh.write(doc)
    print("已生成:", OUT)
    print(f"固件 {size} 字节, sha256 {sha[:16]}…, QMK {tag} @ {commit}")
    print(f"图片: 键位图 1 + status {len(preview.LEFT_STATES)} + anim 8 + logo 1")


if __name__ == "__main__":
    main()
