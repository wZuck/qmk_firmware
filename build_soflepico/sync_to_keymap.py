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
| `keymap_layers.png` | `build_soflepico/keymap_layers.png`（四层键位图） |
| `oled_overview.png` | `build_soflepico/oled_preview/oled_overview.png`（三种画面总览） |
| `anim.gif` | `build_soflepico/oled_preview/anim.gif`（动画 8 帧循环） |
| `1x/` `4x/` | `build_soflepico/oled_preview/1x|4x/`（status 6 张 + anim 8 张 + logo 1 张） |
| 键位表文字版 | 同目录上一级的 `keymap.md` |

OLED 三种画面（status / anim / logo）的内容、切换键和换图方法，
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

    # 键位表：图片路径改写成 preview/ 下
    src = open(os.path.join(HERE, "keymap.md")).read()
    open(os.path.join(DST, "keymap.md"), "w").write(src.replace("](keymap_layers.png)", "](preview/keymap_layers.png)"))

    shutil.copy2(os.path.join(HERE, "keymap_layers.png"), PREV)
    for name in ("oled_overview.png", "anim.gif"):
        shutil.copy2(os.path.join(HERE, "oled_preview", name), PREV)
    n = 0
    for sub in ("1x", "4x"):
        for f in sorted(os.listdir(os.path.join(HERE, "oled_preview", sub))):
            if f.endswith(".png"):
                shutil.copy2(os.path.join(HERE, "oled_preview", sub, f), os.path.join(PREV, sub, f))
                n += 1

    open(os.path.join(PREV, "README.md"), "w").write(README)
    print(f"已同步到 {DST}")
    print(f"  keymap.md + preview/{{keymap_layers.png, oled_overview.png, anim.gif, README.md, 1x|4x ({n} 张)}}")


if __name__ == "__main__":
    main()
