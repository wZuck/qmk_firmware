# sofle_pico `default` 固件 —— 构建产物与说明

本目录保存 **sofle_pico `default` keymap** 的编译产物，以及这份固件的功能说明与烧录方法。
（本目录是纯产物目录，不参与 QMK 构建；重新编译不会自动更新这里，需要手动重新拷贝。）

## 1. 构建信息

| 项目 | 值 |
|---|---|
| 键盘 | `sofle_pico`（RP2040 / Raspberry Pi Pico，分体，左右各一个 EC11） |
| keymap | `default` |
| 编译命令 | `qmk compile -kb sofle_pico -km default` |
| QMK 版本 | tag `0.34.4`，commit `08c662f286`（2026-09-05），分支 `master` |
| 构建时间 | 2026-09-30 |
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
| `keymap.md` | **键位图与分层说明**：每层有哪些键、怎么换层 |
| `keymap_layers.svg` | **四层键位图（矢量）**：按真实坐标绘制，放多大都不糊 |
| `keymap_layers.png` | 同一张图的光栅版，默认 2 倍（1468×3300），可 `python3 gen_keymap_image.py 4` 出 4 倍 |
| `gen_keymap_image.py` | 由 `keymap.c` + `keyboard.json` 重新生成键位图（PNG + SVG）与 `keymap.md` |
| `oled_preview/` | **OLED 显示内容预览**：信息屏 13 种 + 四组动画共 32 帧 + logo，含 `1x`/`4x`/4 个 GIF/总览图 |
| `index.html` | **一页看全**：固件信息 + 键位图 + OLED 三种画面（打开即可，图片走相对路径） |
| `gen_index.py` | 重新生成 `index.html`（自动带上 uf2 的 SHA-256、QMK 版本、图片清单） |
| `sync_to_keymap.py` | 把 `keymap.md` 和预览图同步到 `keyboards/sofle_pico/keymaps/default/` |

> `.uf2` 与 `.hex`/`.bin` 内容等价，选一个用即可。
> 改了 `keymap.c` 之后，`python3 gen_keymap_image.py` 可以刷新键位图与说明。

`.uf2` 校验值（SHA-256），用于确认烧录的就是这一份：

```
d6b04b43d725573bb98cbd326effe9cd29637d21d10992def1115871b939e59e  sofle_pico_default.uf2
```

## 3. 烧录方法

左右两半要**分别烧各自那一份**（同一份 uf2 文件即可，靠 EEPROM 里的手性 `EE_HANDS` 区分左右；
首次使用或换主板时，请确认 EEPROM 手性已设置，否则用 `uf2-split-left` / `uf2-split-right` 区分）。

进入 bootloader：按住 Pico 上的 `BOOT` 键 → 按一下 `RST` → 先松 `RST` 再松 `BOOT`，
电脑上会出现名为 `RPI-RP2` 的 U 盘，把 `.uf2` 拖进去即可。

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

### 4.2 其它

- 层：`QWERTY`(0) / `LOWER`(1) / `RAISE`(2) / `ADJUST`(3)（Colemak 层已删除），`LOWER`+`RAISE` 三键组合出 `ADJUST`。
- Mac/Win 模式在 `ADJUST` 层切换，选择存 EEPROM；`QK_BOOT`、`EE_CLR` 也在该层。
- OLED：每一半都能在 10 个画面之间切换（见 4.3），切换键是 `ADJUST` 层左右各一个 `OLED` 键（按住可快速翻页）。
- VIA 已启用（层数用核心默认的 4 层），可用 VIA 网页版改键。

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

## 5. 已验证

- `qmk compile -kb sofle_pico -km default` 通过，无 warning 阻断。
- 从 ELF 中核对 `.rodata.encoder_map`（32 字节 = 4 层 × 2 编码器 × 2 方向 × 2 字节）：

  ```
  层0: a900 aa00 | ab00 ac00   -> 左 CW=VOLU CCW=VOLD   右 CW=MNXT CCW=MPRV
  层1-3: 0100 0100 ...          -> 全部 KC_TRNS（穿透到第 0 层）
  ```

- 从 ELF 中核对按键：`keymaps[0][4][5] = 0x00a8`（`KC_MUTE`）、`keymaps[0][9][5] = 0x00ae`（`KC_MPLY`）。
- 从 ELF 中核对 `keymaps` 为 4 层（480 字节），`ADJUST` 层上
  `[1,3] = [6,2] = 0x7E40`（`OLED_NEXT`）、`[1,5] = 0x7C03`（`EE_CLR`）。
- 从 ELF 中核对 `oled_anim` = `0x8000` = 32768 字节 = 4 组 × 8 帧 × 1024 字节，
  且每一帧与 `oled_anim.h` 逐字节一致（预览就是面板上会显示的内容）。

## 6. 注意事项

1. **方向反了怎么办**：若某一侧旋钮左右拧反，把该侧 `ENCODER_CCW_CW(a, b)` 里的两个键码对调
   （第一个是逆时针/左旋，第二个是顺时针/右旋），重新编译即可。这与编码器 A/B 相序有关。
2. **VIA 的 EEPROM 行为**：因为启用了 VIA，编码器映射与键位在运行时是**从 EEPROM 读的**，
   `encoder_map` / `keymaps` 只在 EEPROM 首次初始化时写入一次。如果之前已经烧过 VIA 版固件
   且 EEPROM 仍然有效，这次的新映射**不会自动生效**，需要：
   - 在 VIA 里重新设置编码器映射，或
   - 清一次 EEPROM：**`ADJUST` 层已经放了一个 `EE_CLR` 键**（左手 `T` 键位置），按一下即可，
     或者用 VIA 的 Reset Keymap。
   - 本次改动删了一个层、加了两个 `OLED` 键和一个 `EE_CLR` 键，所以**烧完必须先清一次 EEPROM**，
     否则键盘上跑的还是旧键位。
3. 两半都必须烧新固件；只烧一半会出现两层版本不一致的奇怪现象。
4. 更换旋钮分辨率等编码器硬件配置后，**带旋钮的那一半必须重新烧录**。

## 7. 相关源文件

- `keyboards/sofle_pico/keyboard.json`：矩阵、编码器引脚、RGB、USB 信息
- `keyboards/sofle_pico/config.h`：分体/串口/OLED/鼠标/编码器等宏
- `keyboards/sofle_pico/rules.mk`：串口驱动 `SERIAL_DRIVER = vendor`
- `keyboards/sofle_pico/post_config.h`：右手 bootmagic 引脚
- `keyboards/sofle_pico/keymaps/default/keymap.c`：键位、旋钮映射、OLED、自定义键码
- `keyboards/sofle_pico/keymaps/default/config.h`：`SPLIT_LAYER_STATE/LED_STATE/WPM_ENABLE`
- `keyboards/sofle_pico/keymaps/default/rules.mk`：`ENCODER_MAP_ENABLE` / `VIA_ENABLE` / `WPM_ENABLE`
