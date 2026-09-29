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
| `anim` | 大眼小怪物的 8 帧动画（8 fps） | 右半 |
| `logo` | Sofle Pico 静态图（`oled_image.h`，64x96） | — |

- 切换键：`ADJUST` 层上**左右各一个 `OLED` 键**（左半在 `E` 键位置，右半在镜像的 `O` 键位置）。
  按一下切换**本侧**画面：status → anim → logo → status。
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
│   ├── status_01_idle_win.png                    状态屏：空闲、无修饰键
│   ├── status_02_typing_wpm42.png                状态屏：打字中 WPM 42 / 峰值 58
│   ├── status_03_mac_wpm76.png                   状态屏：Mac 模式、按住 Alt
│   ├── status_04_layer_lower_wpm55.png           状态屏：按住 LOWER + Shift
│   ├── status_05_layer_raise_wpm12.png           状态屏：按住 RAISE + Ctrl
│   ├── status_06_adjust_mac_wpm88_caps.png       状态屏：四个修饰键全按、Caps Lock 开
│   ├── anim_00..07.png                           动画 8 帧
│   └── screen_logo.png                           logo 静态图
├── 4x/                        ← 同样 15 张，256 x 512 放大版，方便看
├── anim.gif                   ← 动画循环（8 帧，8 fps）
├── oled_overview.png          ← 一图看全：三种画面
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
   8    | PEAK    88     |   本轮打字最高 WPM（停手 5 秒后归零）
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

## 四、anim 画面

大眼小怪物的弹跳循环：整体上下弹跳、落地时压扁、期间眨眼、双臂一上一下摆动、眼珠左右看，
8 帧、8 fps（`SOFLE_ANIM_FPS`），每帧都是整块 64x128 画布（1024 字节）。

角色是按参考图（圆头 + 两只大眼睛 + 椭圆身体 + 平伸手臂 + 两条腿）测出比例后，
用 `line` / `ellipse` / `disc` 这些图元重新画成 1 bit 的，画法与图层顺序也照参考图来：
先腿 → 身体（挖空内部，腿在体内的一段被遮住）→ 头（盖住身体顶弧）→ 眼睛（盖住头轮廓）→ 瞳孔。

| 帧 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 垂直位移 | 0 | −3 | −9 | −14 | −16 | −14 | −9 | −3 |
| 身体 | 压扁 | 略扁 | 拉伸 | 拉伸 | 拉伸 | 略扁 | 略扁 | 压扁 |
| 眼睛 | 睁 | 睁 | 睁 | 睁 | 闭 | 闭 | 睁 | 睁 |

## 五、logo 画面

`oled_image.h` 是一张 64x96 的 1 bit 图（12 个 page、768 字节），画在画布最上面，
下面 32 px 留空。由 `img2c.py` 从 PNG 生成。

## 六、换成自己的图

三个脚本都写在 `keyboards/sofle_pico/keymaps/default/` 里，都是纯标准库：

| 目的 | 脚本 | 产物 |
|---|---|---|
| 改动画角色/动作 | `make_mascot_anim.py` | `oled_anim.h`（当前用的） |
| 要回原来的心形占位动画 | `make_anim.py` | `oled_anim.h` |
| 把自己的 PNG 转成屏幕图 | `img2c.py` | 任意头文件，如 `oled_image.h` |

```sh
cd keyboards/sofle_pico/keymaps/default
python3 make_mascot_anim.py
python3 img2c.py my_picture.png --height 96 --helper-color ff00ff -o my_logo.h
```

改完记得：重新编译烧录 → 回到本目录跑 `gen_oled_preview.py` 刷新预览。

## 七、几个实际注意点

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
