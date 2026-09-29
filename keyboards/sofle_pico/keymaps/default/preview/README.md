<!-- 由 build_soflepico/sync_to_keymap.py 同步，勿手改 -->

# keymap 预览图（同步副本）

这里是为了跟源码放在一起而同步过来的副本，**原始文件在 `build_soflepico/`**：

| 内容 | 原始位置 |
|---|---|
| `keymap_layers.svg` | `build_soflepico/keymap_layers.svg`（四层键位图，矢量，放多大都不糊） |
| `keymap_layers.png` | `build_soflepico/keymap_layers.png`（同一张图，2 倍光栅） |
| `oled_overview.png` | `build_soflepico/oled_preview/oled_overview.png`（三种画面总览） |
| `reference.png` | `build_soflepico/oled_preview/reference.png`（角色的参考原图） |
| `anim_*.gif` | `build_soflepico/oled_preview/anim_*.gif`（四组动画各自的 8 帧循环） |
| `1x/` `4x/` | `build_soflepico/oled_preview/1x|4x/`（status 6 张 + 动画 40 张 + logo 1 张） |
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
