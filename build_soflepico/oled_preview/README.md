# OLED 显示内容预览

这个文件夹放的**不是照片或截图**，而是按固件里真正的绘图代码**逐字节重放**出来的像素图 ——
也就是键盘装上 OLED 之后会显示的东西。

数据来源都是真表，不是手抄的：

| 用到的东西 | 来源 |
|---|---|
| 6x8 正文字体 | `drivers/oled/glcdfont.c`（驱动真正使用的字体表） |
| 12x16 大字（层名） | `keyboards/sofle_pico/keymaps/default/oled_bigfont.h` |
| 动画帧 | `keyboards/sofle_pico/keymaps/default/oled_anim.h` |
| 静态图 | `keyboards/sofle_pico/keymaps/default/oled_image.h` |
| 画法/坐标/进度条 | `keymap.c` 的 `render_status()` / `render_wpm()` / `render_rule()` / `render_logo()` |
| 显存布局 | `drivers/oled/oled_driver.c`：`buffer[page * 64 + x]`，bit `y % 8`，LSB 最上一行 |

## 一、三种画面，各自切换

左右两半**各自独立**决定自己显示什么，每一种都在 `ADJUST` 层有一个自己的按键：

| 画面 | 内容 | 默认 |
|---|---|---|
| `status` | 层名大字 · Mac/Win · 实时修饰键 · 峰值 WPM · 当前 WPM 与进度条 · Caps Lock | 左半 |
| `stats` | 统计：按键数（本半边）· WPM · 峰值 · 当前层 · 运行时间 · Caps | — |
| `graph` | WPM 曲线：2 倍大号当前 WPM + 最近 21 秒柱状图 | — |
| `layers` | 四个层的开关状态（看清 LOWER+RAISE → ADJUST）| — |
| `anim 0` bounce | 跳 + 落地压扁 + 眨眼 + 摆手 | 右半 |
| `anim 1` wave | 站着挥手打招呼 | — |
| `anim 2` walk | 原地踏步，手臂反向摆 | — |
| `anim 3` dance | 左右摇摆，边上飘音符 | — |
| `anim 4` sleep | 闭眼呼吸，飘 z | — |
| `logo` | Sofle Pico 静态图（`oled_image.h`，64x96） | — |

五组动画都是 8 帧、8 fps 的 64x128 循环，一共 40 KB。

- 切换键：`ADJUST` 层上**左右各一个 `OLED` 键**（左半在 `E` 键位置，右半在镜像的 `O` 键位置）。
  按一下切换**本侧**画面：status → stats → graph → layers → anim 0 → … → anim 4 → logo → status。
- **按住不放**会每 400 ms 自动往下翻（`SOFLE_OLED_HOLD_MS`），所以 11 个画面不用点十几次。
- 两边互不影响：左半可以放动画、右半可以放状态屏。
- 选择只存在 RAM，重启回到默认（左 status / 右 anim）。
- **开机动画**：上电后两半都先播约 1.8 秒动画（`SOFLE_BOOT_MS`），然后才切到各自选的画面。
- 切换的瞬间固件会先清屏，所以不会留下上一屏的残影。
- 为什么不用普通的键码处理：`process_record_user()` 只在主机侧运行，从机收不到键码。
  所以两个半边各自在 `housekeeping_task_user()` 里扫**自己那半边**的矩阵，
  看 `ADJUST` 层那个位置是不是 `OLED_NEXT`，是就切自己的画面。

## 二、目录内容

```
oled_preview/
├── 1x/                        ← 64 x 128 真实像素，面板上就是这样的
│   ├── status_01..06_*.png                       状态屏 6 种（空闲/打字/Mac/LOWER/RAISE/ADJUST）
│   ├── stats_01..02_*.png                        统计屏 2 种（刚上电 / 用了一会儿）
│   ├── graph_01..02_*.png                        WPM 曲线 2 种（空闲 / 打字中）
│   ├── layers_01..03_*.png                       层状态 3 种（基础 / LOWER / ADJUST）
│   ├── anim_bounce_00..07.png                    动画 5 组，每组 8 帧
│   ├── anim_wave_00..07.png
│   ├── anim_walk_00..07.png
│   ├── anim_dance_00..07.png
│   ├── anim_sleep_00..07.png
│   └── screen_logo.png                           logo 静态图
├── 4x/                        ← 同样 54 张，256 x 512 放大版，方便看
├── anim_bounce.gif            ← 每组动画一个循环 GIF（共 5 个）
├── anim_wave.gif  anim_walk.gif  anim_dance.gif  anim_sleep.gif
├── oled_overview.png          ← 一图看全：状态屏 + 五组动画的全部帧 + logo
└── gen_oled_preview.py        ← 生成器
```

重新生成（改过 `keymap.c` 或 OLED 相关头文件之后）：

```sh
cd build_soflepico/oled_preview
python3 gen_oled_preview.py
```

## 三、status 画面

画布 64 宽 x 128 高，文字每行 8px、共 16 行，每行 10 个字符（6px 一个字）。

```
行  0  +----------------+
        |                |
   1    |  ------------- |   分隔线（单像素）
   2    |      LOWER     |   层名大字，12x16，占 2 行
   3    |                |
   4    |  ------------- |   分隔线
   6    | MODE WIN       |   Mac/Win 模式（MODE WIN / MODE MAC）
   7    | MODS C..G      |   实时修饰键：C S A G，没按住显示 '.'
   8    | PEAK    88     |   最近 21 秒内的最高 WPM（和 graph 屏同一个历史缓冲）
   9    | WPM    42      |   当前打字速度（0-99，两位数）
  10    | [----bar-----] |   WPM 进度条（底部有一条基线）
  13    | CAPS OFF       |   Caps Lock 状态
        +----------------+
```

层名大字有四种：`BASE`、`LOWER`、`RAISE`、`ADJ`（ADJUST，64px 只放得下 3 个大字）。

哪一半显示状态屏都不影响它工作：`is_keyboard_left()` 决定"我是哪半边"，
这来自 EEPROM 里的手性，而不是插 USB 的那一半。所以左半可能是在从机状态，
它显示的层、LED、WPM 都得靠 split 链路同步过来 —— 这就是 keymap 的 `config.h` 里
`SPLIT_LAYER_STATE_ENABLE`、`SPLIT_LED_STATE_ENABLE`、`SPLIT_WPM_ENABLE` 的作用。

## 四、anim 画面（五组）

五组都是同一个大眼小怪物，8 帧、8 fps（`SOFLE_ANIM_FPS`），每帧整块 64x128 画布（1024 字节）：

| # | 名字 | 动作 |
|---|---|---|
| 0 | `bounce` | 上下弹跳、落地压扁、眨眼、双臂一上一下摆、眼珠转 |
| 1 | `wave` | 站着不动，右手抬起挥动打招呼，中途眨一次眼 |
| 2 | `walk` | 原地踏步：两脚交替抬起并前移，手臂反向摆，身体随步起伏 |
| 3 | `dance` | 整体左右倾斜 ±7°，双臂上下甩，嘴角上方飘两个音符（字体里的 ♪ ♫） |
| 4 | `sleep` | 眼睛闭着，身体随呼吸起伏，三个大小不同的 `z` 向上飘 |

想加一组：在 `keyboards/sofle_pico/keymaps/default/make_animations.py` 的 `ANIMATIONS`
里加一项（给 `dy`/`squash`/`rot`/`arm_l`/`arm_r`/`lift_l`/`lift_r`/`blink`/`look` 这些
逐帧参数表），重跑脚本 → 重新编译 → 回来重跑本目录的生成器。

除了角色，还可以用 `notes=True` / `sleep_z=True` 那种装饰，或者直接用 `Grid.glyph()`
把字体里的任意字符画到画布上。

角色是按参考图（圆头 + 两只大眼睛 + 椭圆身体 + 平伸手臂 + 两条腿）测出比例后，
用 `line` / `ellipse` / `disc` 这些图元重新画成 1 bit 的，画法与图层顺序也照参考图来：
先腿 → 身体（挖空内部，腿在体内的一段被遮住）→ 头（盖住身体顶弧）→ 眼睛（盖住头轮廓）→ 瞳孔。

| 帧 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 垂直位移 | 0 | −3 | −9 | −14 | −16 | −14 | −9 | −3 |
| 身体 | 压扁 | 略扁 | 拉伸 | 拉伸 | 拉伸 | 略扁 | 略扁 | 压扁 |
| 眼睛 | 睁 | 睁 | 睁 | 睁 | 闭 | 闭 | 睁 | 睁 |

## 五、另外三种信息屏

- **stats**：`KEY 12345`（本半边按键数，5 位）· `WPM` · `PEAK` · `LAYER` · `UP 03:21`（上电运行时间）· `CAPS`。
  按键数是**本半边**扫到的次数——从机收不到主机的键码，所以两半各自计数。
- **graph**：顶部 2 倍大号当前 WPM，下面把最近 21 秒的 WPM 画成 21 根柱子（每根 2px 宽、3px 一格，
  高度按 100 WPM 占满算）。WPM 本身通过 split 同步，所以两半的曲线一致。
- **layers**：`BASE`/`LOWER`/`RAISE`/`ADJ` 四行 `ON`/`OFF`，按住 LOWER+RAISE 时能看到 `ADJ` 变 `ON`。

## 六、logo 画面

`oled_image.h` 是一张 64x96 的 1 bit 图（12 个 page、768 字节），画在画布最上面，
下面 32 px 留空。由 `img2c.py` 从 PNG 生成。

## 七、换成自己的图

三个脚本都写在 `keyboards/sofle_pico/keymaps/default/` 里，都是纯标准库：

| 目的 | 脚本 | 产物 |
|---|---|---|
| 改/加动画（角色与动作） | `make_animations.py` | `oled_anim.h`（五组动画都在里面） |
| 层名大字用的 2x 字体 | `make_bigfont.py` | `oled_bigfont.h` |
| 画布模板（64x128 的图画纸） | `make_template.py` | `oled_template*.png` |
| 把自己的 PNG 转成屏幕图 | `img2c.py` | 任意头文件，如 `oled_image.h` |

```sh
cd keyboards/sofle_pico/keymaps/default
python3 make_animations.py            # 重新生成五组动画
python3 make_bigfont.py               # 需要用到大字时
python3 img2c.py my_picture.png --height 96 --helper-color ff00ff -o my_logo.h
```

改完记得：重新编译烧录 → 回到本目录跑 `gen_oled_preview.py` 刷新预览。

## 八、几个实际注意点

1. **面板是单色的**：SSD1306 128x64，只有"亮/灭"，预览里的青白色只是常见的显示颜色，
   实际颜色取决于你买的模块（白、蓝、黄蓝双色等）。
2. **屏幕方向**：面板装成竖屏，固件用 `SOFLE_OLED_ROTATION = OLED_ROTATION_90` 把
   64x128 的逻辑画布转过去。本预览按**逻辑画布**渲染（line 0 在上）。如果装好后某一半
   上下颠倒，把 `keymap.c` 里的 `SOFLE_OLED_ROTATION` 改成 `OLED_ROTATION_270`
   （两者差 180°）重新编译即可，本预览不受影响。
3. **每行只有 10 个字符**，而且状态屏的每一行都刻意写成**恰好 9 个字符**：
   驱动补空格到行尾时会踩到下一行，9 个字符刚好只补 1 个空格，落到正确位置。
   改状态屏文字时别改成 10 个字符。
4. **VIA 的 EEPROM**：键位（含 `ADJUST` 层的 `OLED` / `EE_CLR` 键）在 VIA 启用时是从 EEPROM
   读的，改了 keymap 要先清一次 EEPROM（`ADJUST` 层的 `EE_CLR` 键）才会生效。
5. 这个预览是**仿真**，不含 OLED 的亮度、对比度、像素间距等物理效果。
