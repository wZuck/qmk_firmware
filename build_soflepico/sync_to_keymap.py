#!/usr/bin/env python3
"""把说明与预览图同步一份到 keymap 目录，跟源码放在一起。

产物（都在 keyboards/sofle_pico/keymaps/default/ 下）：
  keymap.md              键位表，图片路径改写成 preview/keymap_layers.png
  preview/README.md      说明这是同步副本、怎么刷新
  preview/keymap_layers.png
  preview/oled_overview.png
  preview/anim.gif
  preview/1x/*.png       15 张真实像素
  preview/4x/*.png       15 张放大版

用法： python3 sync_to_keymap.py
"""

import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DST = os.path.join(ROOT, "keyboards/sofle_pico/keymaps/default")
PREV = os.path.join(DST, "preview")

README = """<!-- 由 build_soflepico/sync_to_keymap.py 同步，勿手改 -->

# keymap 预览图（同步副本）

这里是为了跟源码放在一起而同步过来的副本，**原始文件在 `build_soflepico/`**：

| 内容 | 原始位置 |
|---|---|
| `keymap_layers.svg` | `build_soflepico/keymap_layers.svg`（四层键位图，矢量，放多大都不糊） |
| `keymap_layers.png` | `build_soflepico/keymap_layers.png`（同一张图，2 倍光栅） |
| `oled_overview.png` | `build_soflepico/oled_preview/oled_overview.png`（三种画面总览） |
| `reference.png` | `build_soflepico/oled_preview/reference.png`（角色的参考原图） |
| `anim_*.gif` | `build_soflepico/oled_preview/anim_*.gif`（四组动画各自的 8 帧循环） |
| `snow_pair.gif` `snow_pair_inv.gif` `snow_polarities.png` `mascot_polarities.png` | `build_soflepico/oled_preview/`（雪人正/反两帧、两套图的正反对照） |
| LED 灯效的 GIF | 在 `build_soflepico/led_effects/fx_*.gif`（9 个灯效，用真实灯效源码逐帧重放出来的）；这里不重复放一份，页面上看 `build_soflepico/index.html` 的「LED 灯效」一节 |
| `1x/` `4x/` | `build_soflepico/oled_preview/1x|4x/`（status 6 张 + 小怪物动画 32 张 + 反色 32 张 + 雪人正/反 4 张） |
| 键位表文字版 | 同目录上一级的 `keymap.md` |

OLED 各个画面（status / stats / graph / layers / anim 小怪物正反 / snow 雪人正反）的内容、切换键和换图方法，
见 `build_soflepico/oled_preview/README.md`。

改了 `keymap.c` 或 OLED 头文件之后，重新生成并同步：

```sh
cd build_soflepico
python3 gen_keymap_image.py          # 刷新键位图 / keymap.md
python3 oled_preview/gen_oled_preview.py   # 刷新 OLED 预览
python3 sync_to_keymap.py            # 同步到 keymap 目录（本目录）
```

> 图片是仿真：按固件里的绘图代码逐字节重放，不是拍照。
"""


def main():
    os.makedirs(os.path.join(PREV, "1x"), exist_ok=True)
    os.makedirs(os.path.join(PREV, "4x"), exist_ok=True)

    # 目标目录先清空图片，避免上一版命名的残留（动画改名/增删时尤其明显）
    for sub in ("", "1x", "4x"):
        d = os.path.join(PREV, sub)
        for f in os.listdir(d):
            if f.endswith((".png", ".gif", ".svg")):
                os.remove(os.path.join(d, f))

    # 键位表：图片路径改写成 preview/ 下
    src = open(os.path.join(HERE, "keymap.md")).read()
    # build 侧两个文件都跟 keymap.md 同目录，所以文档里是裸路径；同步过去两份图
    # 都落在 preview/ 下，链接跟着改。
    for name in ("keymap_layers.png", "keymap_layers.svg"):
        src = src.replace("](%s)" % name, "](preview/%s)" % name)
    open(os.path.join(DST, "keymap.md"), "w").write(src)

    for name in ("keymap_layers.png", "keymap_layers.svg"):
        shutil.copy2(os.path.join(HERE, name), PREV)
    shutil.copy2(os.path.join(HERE, "oled_preview", "oled_overview.png"), PREV)
    shutil.copy2(os.path.join(HERE, "oled_preview", "reference.png"), PREV)
    gifs = [f for f in sorted(os.listdir(os.path.join(HERE, "oled_preview"))) if f.endswith(".gif")]
    for name in gifs:
        shutil.copy2(os.path.join(HERE, "oled_preview", name), PREV)
    n = 0
    for sub in ("1x", "4x"):
        for f in sorted(os.listdir(os.path.join(HERE, "oled_preview", sub))):
            if f.endswith(".png"):
                shutil.copy2(os.path.join(HERE, "oled_preview", sub, f), os.path.join(PREV, sub, f))
                n += 1

    open(os.path.join(PREV, "README.md"), "w").write(README)
    print(f"已同步到 {DST}")
    print(f"  keymap.md + preview/{{keymap_layers.png, oled_overview.png, {len(gifs)} 个 OLED GIF, "
          f"README.md, 1x|4x ({n} 张)}}")


if __name__ == "__main__":
    main()
