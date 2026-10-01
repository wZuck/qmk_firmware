# sofle_pico `default` 固件 —— 构建产物与说明

本目录保存 **sofle_pico `default` keymap** 的编译产物，以及这份固件的功能说明与烧录方法。
（本目录是纯产物目录，不参与 QMK 构建；重新编译不会自动更新这里，需要手动重新拷贝。）

## 1. 构建信息

| 项目 | 值 |
|---|---|
| 键盘 | `sofle_pico`（RP2040 / Raspberry Pi Pico，分体，左右各一个 EC11） |
| keymap | `default` |
| 编译命令 | `qmk compile -kb sofle_pico -km default` |
| QMK 版本 | tag `0.34.5-16-gef8f9327cc`，commit `ef8f9327cc`，分支 `master` |
| 构建时间 | 2026-10-01 |
| 源文件 | `keyboards/sofle_pico/`（工作区修改，尚未提交） |

> 注意：仓库根目录的 `.gitignore` 里有 `*.uf2`，所以本目录中的固件不会被 git 跟踪；
> 本目录整体处于未跟踪状态，不会被提交，也不会影响 QMK 编译。

## 2. 文件清单

| 文件 | 用途 |
|---|---|
| `sofle_pico_default.uf2` | **烧录用固件**，拖到 RPI-RP2  U 盘即可 |
| `sofle_pico_default.hex` | Intel HEX，给 SWD / 其他烧录器用 |
| `sofle_pico_default.bin` | 裸二进制镜像 |
| `sofle_pico_default.elf` | 带调试符号的可执行文件（gdb / 反汇编用） |
| `sofle_pico_default.map` | 链接映射表（查符号地址、占用大小用） |
| `matrix_map_left.svg` / `.png` | **左手矩阵排查图**：每个键标出物理键位 + `rXcY`，按实测通/不通着色，边框颜色=所属列 |
| `pico_pinout.svg` / `.png` | **Pico 引脚对照图**：40 脚里哪些是矩阵行/列、RGB、OLED、旋钮、TRRS |
| `led_map.svg` / `.png` | **逐键 RGB 灯位图**：58 颗灯的全局索引、本半灯带序号、矩阵位置、灯带走向（数据来自 `keyboard.json`，并与 `.build` 里已编译的 `g_led_config` 逐项核对） |
| `gen_matrix_image.py` / `gen_pico_pinout.py` / `gen_led_map.py` | 生成上面三张排查图 / 灯位图 |
| `hardware_check.md` | **硬件排查指南**：从引脚自检、万用表测量到换 Pico 的完整流程 |
| `keymap.md` | **键位图与分层说明**：每层有哪些键、怎么换层 |
| `keymap_layers.svg` | **四层键位图（矢量）**：按真实坐标绘制，放多大都不糊 |
| `keymap_layers.png` | 同一张图的光栅版，默认 2 倍（1468×3300），可 `python3 gen_keymap_image.py 4` 出 4 倍 |
| `gen_keymap_image.py` | 由 `keymap.c` + `keyboard.json` 重新生成键位图（PNG + SVG）与 `keymap.md` |
| `oled_preview/fit_reference.py` | 把参考图矢量化（Hough 找圆、最小二乘拟合椭圆），算出角色各图元的参数 |
| `oled_preview/reference.png` | 参考原图（角色的出处） |
| `oled_preview/` | **OLED 显示内容预览**：信息屏 13 种 + 四组动画共 32 帧 + logo，含 `1x`/`4x`/4 个 GIF/总览图 |
| `index.html` | **一页看全**：固件信息 + 键位图 + LED 灯效（互动播放器 + 8 段 GIF）+ OLED 三种画面（打开即可，图片/数据走相对路径，不用起服务器） |
| `gen_index.py` | 重新生成 `index.html`（自动带上 uf2 的 SHA-256、QMK 版本、图片清单） |
| `led_effects/` | **灯效逐帧采集器**：`harness.c` 在电脑上编译真实灯效源码 → `led_frames.json`（详见 `led_effects/README.md`） |
| `gen_led_effects.py` | 把 `led_frames.json` 画成 `led_effects/fx_*.gif`，并生成网页播放器要的 `led_effects.js` |
| `led_player.js` | `index.html` 里那块互动播放器（点灯效、拖亮度/色相/速度） |
| `verify_keymap.py` | 从编译好的 ELF 里读回 `keymaps` / `encoder_map`，按层打印键码名字 |
| `sync_to_keymap.py` | 把 `keymap.md` 和预览图同步到 `keyboards/sofle_pico/keymaps/default/` |

> `.uf2` 与 `.hex`/`.bin` 内容等价，选一个用即可。
> 改了 `keymap.c` 之后，`python3 gen_keymap_image.py` 可以刷新键位图与说明。

`.uf2` 校验值（SHA-256），用于确认烧录的就是这一份：

```
830ae560aa142f5e217eae930b78fbaae856ce79266d107d001c47518b29f2ef  sofle_pico_default.uf2
bdec258118759d2b5c6f6a87b63375c2d60852d08ff47156949b283b54ea47a6  sofle_pico_default_split-left.uf2
f7c7fd1148767ccc9e53e6a9f6f1b84ef5fa0aa5517a81f420609c6df07cdd0d  sofle_pico_default_split-right.uf2
```

（`split-left` / `split-right` 不是 `qmk compile` 能直接出的目标：按
`platforms/chibios/flash.mk:50-64`，`uf2-split-left` 这个 goal 只是在编译时多加一个
`-DINIT_EE_HANDS_LEFT`（右半是 `-DINIT_EE_HANDS_RIGHT`，见 `quantum/split_common/split_util.c:160`），
然后**接着往设备里烧**——所以才用等价的
`make sofle_pico:default EXTRAFLAGS=-DINIT_EE_HANDS_LEFT` 只出 uf2 不烧录。
直接跑 `make sofle_pico:default:uf2-split-left` 不插键盘会一直卡在刷写那一步。）

## 3. 烧录方法

左右两半要**分别烧各自那一份**（同一份 uf2 文件即可，靠 EEPROM 里的手性 `EE_HANDS` 区分左右；
首次使用或换主板时，请确认 EEPROM 手性已设置，否则用 `uf2-split-left` / `uf2-split-right` 区分）。

**两个半边必须各烧各的**（这块键盘用手性存在 EEPROM 里的 `EE_HANDS`）。本目录有三个 uf2：

| 文件 | 烧给谁 | 说明 |
|---|---|---|
| `sofle_pico_default_split-left.uf2` | **左手** | 开机时强制把 EEPROM 手性设成「左」 |
| `sofle_pico_default_split-right.uf2` | **右手** | 开机时强制把 EEPROM 手性设成「右」 |
| `sofle_pico_default.uf2` | 任意半边 | 不动 EEPROM 手性；只在你确定手性本来就对时用 |
| `sofle_pico_pintest.uf2` | 排查用 | **引脚电气自检**：每 5 秒打印每个矩阵脚的 `up/down/low` 读回值和桥接检查，把 Pico 拔下来单独跑就能判断"引脚坏"还是"板上走线坏"。详见 `hardware_check.md` |
| `sofle_pico_debug.uf2` | 排查用 | **诊断固件（更精确）**：把原始矩阵变化打到 USB 控制台（`qmk console` 看 `DOWN r2 c4`），USB 插在哪半就测哪半自己的矩阵。对照表见 `keymaps/debug/readme.md` |
| `sofle_pico_probe.uf2` | 排查用 | **诊断固件**：每个按键输出唯一字符（左手小写 a-z/1234，右手大写 A-Z/5678），用来判断哪个矩阵位置没反应、两半手性对不对。关掉了 VIA，所以不受 EEPROM 影响 |

**推荐直接烧前两个**：`EE_HANDS` 的手性只存在 EEPROM 里，一旦清了 EEPROM（比如按过 `EE_CLR`）
或者换了主板，它就变成"两半都以为自己左手"，表现就是按键错乱。带 `split-*` 的两个固件会在启动时
把本半边的极性纠正过来，一劳永逸。

进入 bootloader：按住 Pico 上的 `BOOT` 键 → 按一下 `RST` → 先松 `RST` 再松 `BOOT`，
电脑上会出现名为 `RPI-RP2` 的 U 盘，把对应的 `.uf2` 拖进去即可。

用命令烧录（推荐，会按左右半自动区分）：

```bash
# 左手
make sofle_pico:default:uf2-split-left
# 或
qmk flash -kb sofle_pico -km default -bl uf2-split-left

# 右手
make sofle_pico:default:uf2-split-right
# 或
qmk flash -kb sofle_pico -km default -bl uf2-split-right
```

也可以直接手动拖拽本目录的 `.uf2` 文件。

## 4. 这份固件的功能要点

### 4.1 旋钮（本次改动重点）

| 位置 | 左旋 | 右旋 | 按压 |
|---|---|---|---|
| **左旋钮**（index 0） | 音量 − | 音量 + | `KC_MUTE` 静音（matrix `[4,5]`） |
| **右旋钮**（index 1） | 上一首 `KC_MPRV` | 下一首 `KC_MNXT` | `KC_MPLY` 播放/暂停（matrix `[9,5]`） |

- 旋钮 index 由**物理侧**决定（`is_keyboard_left()`），不是由插 USB 的那一半决定：
  驱动会给右半的 index 加上 `NUM_ENCODERS_LEFT`，所以 `encoder_map` 两个槽位都必须填。
- 右旋钮在**所有层**都有效：只有第 0 层写了键码，上层用 `KC_TRNS` 穿透回基础层。
- 左旋钮在所有层都是音量（第 1 层以上用 `KC_TRNS` 穿透到第 0 层）。
- **例外是 ADJUST(3) 层**：这一层旋钮临时改成调灯——左旋钮 = 亮度（`RM_VALD`/`RM_VALU`）、
  右旋钮 = 灯效速度（`RM_SPDD`/`RM_SPDU`）；连两个旋钮的**按压键**也在这一层变成
  `RM_TOGG`（左，灯开关）和 `RM_NEXT`（右，下一个灯效）。松开换层键就回到音量 / 切歌。

### 4.2 其它

- 层：`QWERTY`(0) / `LOWER`(1) / `RAISE`(2) / `ADJUST`(3)（Colemak 层已删除），`LOWER`+`RAISE` 三键组合出 `ADJUST`。
- Mac/Win 模式在 `ADJUST` 层切换，选择存 EEPROM；`QK_BOOT`、`EE_CLR` 也在该层。
- OLED：每一半都能在 10 个画面之间切换（见 4.3），切换键是 `ADJUST` 层左右各一个 `OLED` 键（按住可快速翻页）。
- VIA 已启用（层数用核心默认的 4 层），可用 VIA 网页版改键。
- 灯光：**逐键 RGB**，左右各 29 颗（共 58 颗）WS2812 兼容灯珠，各自一条灯带、数据脚都是 `GP0`；
  默认开机就亮，**出厂是纯白常亮**（`solid_color`、饱和 0、亮度上限 127、速度 16），**控制键全在 ADJUST 层**（见 4.6），
  也可以用 VIA 的 Lighting 页控制。灯位图见 `led_map.svg` / `led_map.png`。

### 4.3 OLED 画面切换

`ADJUST` 层上**左右各有一个 `OLED` 键**（左半在 `E` 键位置，右半在镜像的 `O` 键位置），
按一下切换**本侧**的画面，依次循环：

| 画面 | 内容 | 默认 |
|---|---|---|
| `status` | 层名大字 · Mac/Win · 实时修饰键（C S A G）· 峰值 WPM · 当前 WPM 与进度条 · Caps Lock | 左半 |
| `stats` | 统计：按键数（本半边）· 当前 WPM · 峰值 WPM · 当前层 · 上电运行时间 · Caps | — |
| `graph` | WPM 曲线：2 倍大号当前 WPM + 最近 21 秒的柱状图 | — |
| `layers` | 四个层的开关状态（能直观看到 LOWER+RAISE 组合出 ADJUST）| — |
| `anim 0` | bounce：跳 + 落地压扁 + 眨眼 + 摆手 | 右半 |
| `anim 1` | wave：站着挥手打招呼 | — |
| `anim 2` | walk：原地踏步，手臂反向摆 | — |
| `anim 3` | sleep：闭眼呼吸，飘 z | — |
| `logo` | `oled_image.h` 的 Sofle Pico 静态图（64x96） | — |

四组动画都是 8 帧、8 fps 的 64x128 循环，一共 32 KB（`SOFLE_ANIM_COUNT` / `SOFLE_ANIM_FRAMES`）。
一共 10 个画面，所以**按住 OLED 键不放会每 400 ms 自动翻一张**，不用点十几次。
`stats` 的按键数是**本半边**扫到的次数（两半各自计数）；`graph` 的 WPM 通过 split 同步，两半画出来一样。
加一组动画只要在 `make_animations.py` 的 `ANIMATIONS` 里加一项，重跑脚本并重新编译——
`oled_screen` 枚举里的动画区间会自动跟着 `SOFLE_ANIM_COUNT` 变。

- 两边互相独立，也互不影响（左半可以是 `anim`，右半可以是 `status`）。
- 选择只存在 RAM，重启回到默认（左 status / 右 anim）；上电后两半都会先播约 1.8 秒动画（`SOFLE_BOOT_MS`）。
- 状态屏上的 `MODS` 行是实时修饰键（按住显示 C/S/A/G，否则显示 `.`）。
- `PEAK`（状态屏和 stats 屏同一个值）= **最近 21 秒内的最高 WPM**，来自 graph 屏用的那个历史缓冲，
  不是上电以来的历史最高。
- 切换瞬间会先清屏，不会留下上一屏的残影。
- 实现上两个半边各自扫自己那半边的矩阵（`housekeeping_task_user()`），
  因为 `process_record_user()` 只在主机侧运行，从机收不到键码。
- 预览图：`oled_preview/`（`status_*.png` / `anim_*.png` / `screen_logo.png`，含 1x / 4x / GIF / 总览）。

### 4.5 按键不正常时的排查

完整的硬件排查流程（怀疑 Pico / 板子坏）见 [`hardware_check.md`](hardware_check.md)：先烧
`sofle_pico_pintest.uf2` 做引脚电气自检，把 Pico 拔下来单独跑即可区分"引脚坏"和"板上走线坏"。


烧 `sofle_pico_probe.uf2`（两个半边都烧），切到英文输入法，打开文本编辑器逐个按键：**按下的键应该打出表里对应的字符**。
想要"哪个矩阵位置真的通了"的原始数据，烧 `sofle_pico_debug.uf2`（USB 插到要测的那半，跑 `qmk console`，
按键会打印 `DOWN r2 c4` / `UP r2 c4`；这样能区分"按键根本没到固件"和"到了但变成了别的字符"）。

完整的对照表和判读方法在 `keyboards/sofle_pico/keymaps/probe/readme.md`，简版：

- 某个键不出字符 → 那个矩阵位置的焊接/二极管/走线有问题
- 整行或整列都不出 → 对应引脚（行 GP9-GP13，列 GP1 GP2 GP3 GP4 GP5 GP8）虚焊
- 出的是**别的**字符 → 位置错位，能反推出是哪一列/行接错了
- 按左手出的是**大写** → 两半手性反了，烧 `split-left` / `split-right` 对应半边
- 单独用某一半（USB 插在它上面）正常，但走分体连接就不行 → 问题在连接线（TRRS / GP16-GP17）而不是按键

### 4.6 ADJUST 层的灯光控制键

ADJUST 层（`LOWER` + `RAISE` 同时按住）上新增了一整组灯光键，左右手各一组：

| 位置 | 键码 | 作用 |
|---|---|---|
| 左手上排 | `RM_TOGG` `RM_NEXT` `RM_PREV` `RM_VALU` `RM_VALD` | 灯开关 / 上一种 / 下一种 / 亮度 ± |
| 右手上排 | `RM_HUEU` `RM_HUED` `RM_SATU` `RM_SATD` `RM_SPDU` `RM_SPDD` | 色相 ± / 饱和 ± / 速度 ± |
| 下排最左 4~5 列（左 5 右 4） | `FX_*` | 9 个灯效直达键（第一个 `FX_WHITE` 是纯白常亮） |
| 左旋钮 / 右旋钮 | —— | 亮度 / 速度 |
| 左旋钮按压 / 右旋钮按压 | `RM_TOGG` / `RM_NEXT` | 灯开关 / 下一个灯效 |

`RM_*` 是这一版 QMK 的灯效键码；老文档里的 `RGB_TOG` / `RGB_MOD` / `RGB_VAI` 这些名字在
0.34 里已经没有了（剩下的 `RGB_M_*` 是旧式模式键，这版内核里也没人处理），所以这里一律用 `RM_*`。

9 个直达灯效（`FX_*` 自定义键码，接在 `SAFE_RANGE` 后面）：

| 键码 | 对应灯效 | 说明 |
|---|---|---|
| `FX_WHITE` | `RGB_MATRIX_SOLID_COLOR` | **纯白常亮（出厂默认）**：`rgb_matrix_sethsv_noeeprom(0, 0, RGB_MATRIX_DEFAULT_VAL)` + 切到 `solid_color`，58 颗灯一起白；一个键等于「恢复出厂灯效」 |
| `FX_CYCLE_OUT_IN` | `RGB_MATRIX_CYCLE_OUT_IN` | 单色光波从键盘中心向外推 |
| `FX_HUE_WAVE` | `RGB_MATRIX_HUE_WAVE` | 彩虹波浪横扫 |
| `FX_RAINBOW_BEACON` | `RGB_MATRIX_RAINBOW_BEACON` | 两道彩虹光柱旋转 |
| `FX_PIXEL_FLOW` | `RGB_MATRIX_PIXEL_FLOW` | 像素流 |
| `FX_JELLYBEAN` | `RGB_MATRIX_JELLYBEAN_RAINDROPS` | 随机彩点 |
| `FX_DIGITAL_RAIN` | `RGB_MATRIX_DIGITAL_RAIN` | 数字雨 |
| `FX_REACTIVE_NEXUS` | `RGB_MATRIX_SOLID_REACTIVE_MULTINEXUS` | 按键涟漪 |
| `FX_TYPING_HEATMAP` | `RGB_MATRIX_TYPING_HEATMAP` | 打字热图 |

- 直达键走 `rgb_matrix_mode_noeeprom()` + `rgb_matrix_enable_noeeprom()`：只改 RAM，
  **重启后回到 EEPROM 里的灯效**，也不会把 VIA Lighting 页的设置写坏；顺手开灯是为了避免
  「关了灯再按预设键，看起来像键坏了」。
- 每个直达键外面套了一层对应的 `ENABLE_RGB_MATRIX_*`：哪天在 `keyboard.json` 里关掉某个灯效，
  这里跟着失效而不是编译报错。没编 RGB 的构建（`probe` 那种）里，这些键会退化成空键。
- 因为键位表本身变了（ADJUST 层新增 20 个键、媒体键挪了位置），`SOFLE_EEPROM_VERSION`
  从 2 提到了 **4**：烧完第一次启动会自动用固件里的键位重写 EEPROM，不用手动清。
- 灯光设置（灯效 / 色相 / 饱和 / 亮度）**存在另一块 EEPROM 里**，`dynamic_keymap_reset()`
  碰不到它。所以版本对不上时顺手调一次 `eeconfig_update_rgb_matrix_default()`，
  老机器烧完新固件才会真的变成纯白常亮；之后你在 VIA / 键盘上改的灯效会一直留着。
- `keyboard.json` 里的默认值是 `default.animation = solid_color`、`hue = 0`、`sat = 0`、
  `val = 127`、`speed = 16`，编译进固件就是 `RGB_MATRIX_DEFAULT_MODE = RGB_MATRIX_SOLID_COLOR`
  等几个宏（可以用 `grep RGB_MATRIX_DEFAULT .build/obj_sofle_pico_default/src/info_config.h` 核对）。

### 4.7 灯效演示动画是怎么来的

`index.html` 里「LED 灯效」那一节的 GIF 和互动播放器，**不是照着效果图画的，是把固件里的灯效代码
拿到电脑上逐帧跑出来的**：

1. `led_effects/harness.c` 在 macOS 上直接编译，include 的是 QMK 仓库里**真实的**灯效源码
   （`quantum/rgb_matrix/animations/*.h` 和 `runners/*.h`）、真实的 `hsv_to_rgb()`，
   以及从已编译固件里抠出来的真实 `g_led_config`（58 颗灯的坐标，见 `led_effects/led_config_gen.h`）。
2. 它按 `g_rgb_timer += dt_ms` 推进 120 帧（默认 68 ms/帧 ≈ 14.7 fps），每帧记下 58 颗灯的 RGB，
   写进 `led_effects/led_frames.json`。按键涟漪 / 打字热图这两种，会按固定节奏（每 3 帧一次，
   约 59 WPM）注入按键事件——画面里的涟漪是「真的在打字」。
   纯白常亮（`FX_WHITE`）是常量输出，不进采集器：`gen_led_effects.py` 直接照固件那条路径算
   （`sat = 0` 时 `hsv_to_rgb()` 走的就是 `rgb.r = rgb.g = rgb.b = CIE1931_CURVE[v]`，v = 127 → 47），
   所以它在演示里只有 1 帧、是个静态画面，`digital_rain` 那样的逐帧动画才来自采集器。
3. `gen_led_effects.py` 把逐帧数据画成 `led_effects/fx_<名字>.gif`，同时生成 `led_effects.js`
   给网页里的互动播放器（`led_player.js`）用。播放器的亮度/色相滑块改的就是 `hsv.v` / `hsv.h`，
   和固件里 `RM_VALU` / `RM_HUEU` 是同一件事；速度滑块相当于换 `RM_SPDU` / `RM_SPDD`。
   `hsv.v` 还要过一道 CIE1931 亮度曲线（固件编译时带 `-DUSE_CIE1931_CURVE`，所以亮度上限 127
   实际只有 47 级），播放器用的是同一张表。

已知的两处不一致（不影响“看到的就是灯效代码算出来的颜色”这个结论，细节见
`led_effects/README.md` 的诚实清单）：
`pixel_flow` / `jellybean_raindrops` 有跨帧状态，而真机上左右两半各持一份，
所以“某一帧是哪几颗灯变色”与分体固件不完全相同（风格一致）；
`digital_rain` 用的是宿主 libc 的 `rand()`，雨滴落点与真机不同（统计特性一致）。

重新生成一整套（固件没变时只需要后两步）：

```bash
cd build_soflepico/led_effects
bash build.sh                                             # -> ./harness
./harness --frames 120 --dt-ms 68 --out led_frames.json    # 逐帧数据（约 500 KB）

cd ..
python3 gen_led_effects.py    # 画 9 个 GIF（led_effects/fx_*.gif）+ 网页播放器数据 led_effects.js
python3 gen_index.py          # 刷新 index.html
```

GIF 的体积是调过的：整段动画共用一张 32 色调色板（每帧各自量化的话，一个 GIF 能到 6.7 MB），
并且每 2 帧取 1 帧（GIF 7.4 fps；网页里的播放器仍然是完整 120 帧 / 14.7 fps）。
想改就 `python3 gen_led_effects.py --scale 0.6 --stride 2 --colors 32`。

> 画图脚本需要 Pillow（`python3 -m pip install pillow`）。采集器只需要 `cc`（macOS 上的 clang）。

采集器的细节、它怎么绕开 chibios、以及和真机还有哪些细微差别，都写在
[`led_effects/README.md`](led_effects/README.md)。

## 5. 已验证

- `qmk compile -kb sofle_pico -km default` 通过，无 warning 阻断。
- **`python3 verify_keymap.py`** 从 ELF 里读回 `keymaps`（480 字节 = 4 层 × 10 行 × 6 列）和
  `encoder_map`（32 字节）并打印键码名字，比手抄十六进制靠谱。这次的输出：

  ```
  ADJUST 层（按物理左右拼好、右手按屏幕顺序）：
    r0 左: RM_TOGG  RM_NEXT  RM_PREV  RM_VALU  RM_VALD  XXXXXXX
    r0 右: RM_HUEU  RM_HUED  RM_SATU  RM_SATD  RM_SPDU  RM_SPDD
    r1 左: QK_BOOT  XXXXXXX  XXXXXXX  OLED_NEXT  CG_TOGG  EE_CLR
    r2 右: XXXXXXX  KC_VOLD  KC_MUTE  KC_VOLU  KC_MPRV  KC_MNXT
    r3 左: FX_WHITE  FX_CYCLE_OUT_IN  FX_HUE_WAVE  FX_RAINBOW_BEACON  FX_PIXEL_FLOW
    r3 右: FX_JELLYBEAN  FX_DIGITAL_RAIN  FX_REACTIVE_NEXUS  FX_TYPING_HEATMAP  KC_MPLY
    旋钮按压: [4,5] = RM_TOGG（左）  [9,5] = RM_NEXT（右）

  encoder_map:
    QWERTY  左 CW=KC_VOLU  CCW=KC_VOLD  | 右 CW=KC_MNXT  CCW=KC_MPRV
    LOWER   4 个方向全部 KC_TRNS（穿透到第 0 层）
    RAISE   同上
    ADJUST  左 CW=RM_VALU  CCW=RM_VALD  | 右 CW=RM_SPDU  CCW=RM_SPDD
  ```

  原始十六进制（ADJUST 层 row0 左、row0 右、下排）：
  `7842 7843 7844 7849 784A 0000` / `7845 7846 7847 7848 784B 784C` /
  `7E46 7E47 7E48 7E49 7E4A` 与 `7E4B 7E4C 7E4D 7E4E 00AE`，和上面一一对应
  （`FX_WHITE = 0x7E46`，8 个灯效依次是 `0x7E47`–`0x7E4E`）。
- 从 ELF 中核对按键：`keymaps[0][4][5] = 0x00a8`（`KC_MUTE`）、`keymaps[0][9][5] = 0x00ae`（`KC_MPLY`）。
- 从 ELF 中核对 `oled_anim` = `0x8000` = 32768 字节 = 4 组 × 8 帧 × 1024 字节，
  且每一帧与 `oled_anim.h` 逐字节一致（预览就是面板上会显示的内容）。
- 灯效演示：`led_effects/harness.c` 跑的 8 个灯效，每一帧 58 颗灯都有非零值、
  且相邻帧确实在变（见 4.7 与 `led_effects/README.md` 里的验证输出）——
  也就是说 GIF 里看到的颜色就是同一份源码在真机上算出来的颜色。
- 默认纯白：从 `.build/obj_sofle_pico_default/src/info_config.h` 核对
  `RGB_MATRIX_DEFAULT_MODE = RGB_MATRIX_SOLID_COLOR`、`RGB_MATRIX_DEFAULT_HUE 0`、
  `RGB_MATRIX_DEFAULT_SAT 0`、`RGB_MATRIX_DEFAULT_VAL 127`、`RGB_MATRIX_DEFAULT_SPD 16`；
  白色本身是 `CIE1931_CURVE[127] = 47`，所以 58 颗灯都是 `RGB(47,47,47)`
  （演示里 `fx_solid_white.gif` 就是这一帧，峰值 47）。

### 4.4 VIA 的按键测试（Key Tester）

VIA 网页版的按键测试是靠 raw HID 读**实时矩阵状态**的，而 QMK 默认把这条请求的返回值全填 0
（防键盘记录），所以会看到"键盘明明能打字，VIA 测试器却没反应"。本 keymap 的 `config.h` 里开了：

```c
#define VIA_INSECURE   // 允许 VIA 读取实时矩阵状态（编译时会提示 susceptible to keyloggers）
```

代价是：任何能访问 raw HID 的程序都能读到你在按哪些键（keylogger 风险）。介意的话把那行删掉重新编译，
VIA 的改键、宏、灯光等功能不受影响，只是测试器会重新变成没反应。

## 6. 注意事项

1. **方向反了怎么办**：若某一侧旋钮左右拧反，把该侧 `ENCODER_CCW_CW(a, b)` 里的两个键码对调
   （第一个是逆时针/左旋，第二个是顺时针/右旋），重新编译即可。这与编码器 A/B 相序有关。
2. **VIA 的 EEPROM 行为**：因为启用了 VIA，编码器映射与键位在运行时是**从 EEPROM 读的**，
   `encoder_map` / `keymaps` 只在 EEPROM 首次初始化时写入一次。如果之前已经烧过 VIA 版固件
   且 EEPROM 仍然有效，这次的新映射**不会自动生效**，需要：
   - 在 VIA 里重新设置编码器映射，或
   - 现在**不需要手动清了**：固件里有个 `SOFLE_EEPROM_VERSION`（这份固件里是 **4**，
     上一次加灯光键时 +1 过），启动时发现 EEPROM 里的版本对不上，
     就自动用固件里的键位重写一遍（`dynamic_keymap_reset()`）。改了层结构之后把这个常量 +1 即可。
   - 仍然保留 `ADJUST` 层的 `EE_CLR` 键（左手 `T` 键位置）作为手动兜底，VIA 的 Reset Keymap 也一样有效。
3. 两半都必须烧新固件；只烧一半会出现两层版本不一致的奇怪现象。
4. 更换旋钮分辨率等编码器硬件配置后，**带旋钮的那一半必须重新烧录**。
5. **ADJUST 层新增的灯光键是要写进 EEPROM 的键位表**：只烧一半固件时，如果手性/EEPROM 版本
   不一致，可能出现一半的 ADJUST 层还是旧键位。稳妥做法是两半都烧 `split-left` / `split-right`。

## 7. 相关源文件

- `keyboards/sofle_pico/keyboard.json`：矩阵、编码器引脚、RGB、USB 信息
- `keyboards/sofle_pico/config.h`：分体/串口/OLED/鼠标/编码器等宏
- `keyboards/sofle_pico/rules.mk`：串口驱动 `SERIAL_DRIVER = vendor`
- `keyboards/sofle_pico/post_config.h`：右手 bootmagic 引脚
- `keyboards/sofle_pico/keymaps/default/keymap.c`：键位、旋钮映射、OLED、自定义键码
- `keyboards/sofle_pico/keymaps/default/config.h`：`SPLIT_LAYER_STATE/LED_STATE/WPM_ENABLE`
- `keyboards/sofle_pico/keymaps/default/rules.mk`：`ENCODER_MAP_ENABLE` / `VIA_ENABLE` / `WPM_ENABLE`
- `keyboards/sofle_pico/keyboard.json` 的 `rgb_matrix.animations`：这一版启用了 41 种灯效
  （没列进去的会编译掉，`RM_NEXT` 也只在这个列表里循环）
- `quantum/rgb_matrix/animations/*.h`：灯效本体；`animations/runners/*.h`：几个通用 effect runner
  （`led_effects/harness.c` 编译的就是这些文件，所以演示动画和真机同源）
