# sofle_pico RGB Matrix 灯效离线 harness

在 macOS 上把 **QMK 仓库里真实的 RGB Matrix 灯效源码**编译成一个原生 C 程序，
逐帧算出 sofle_pico 这块键盘 58 颗 WS2812 的 RGB 值，输出 JSON，供后续脚本
渲染成 GIF / 网页动画。

**没有任何灯效算法被重写**：8 个灯效头文件、6 个 effect runner、
`hsv_to_rgb()`、`scale8()/sin8()/random8()` 全部是本仓库的真实文件；harness 只
提供了真机由 `quantum/rgb_matrix/rgb_matrix.c` 提供的“框架”（全局变量、
`rgb_matrix_set_color()`、limits、按键事件、tick 递推、task 状态机），并且是**照抄**
那个文件，只去掉 split / chibios / EEPROM 分支。

---

## 1. 编译

```bash
cd build_soflepico/led_effects
bash build.sh          # -> ./harness
bash build.sh --clean  # 删掉 harness 和 generated/
```

* 编译器：`cc`（macOS 上就是 clang）。可用 `CC=...` 覆盖。
* 选项：`-std=gnu11 -O2 -Wall -Wextra`（外加几个 `-Wno-*`，见 §9）。
* `build.sh` 每次都会先跑 `extract_led_config.py` 和 `prepare_effects.py`，
  保证 `led_config_gen.h` 和 `generated/` 与仓库/编译产物同步。
* 不依赖 `qmk`、不跑 `qmk compile`、不写仓库里任何其它文件。

链接进去的源文件（除 `harness.c` 外都是仓库真实文件）：

| 文件 | 作用 |
| --- | --- |
| `quantum/color.c` | 真实 `hsv_to_rgb()` / `hsv_to_rgb_nocie()` |
| `quantum/led_tables.c` | 真实 `CIE1931_CURVE[256]` 亮度曲线表 |
| `lib/lib8tion/lib8tion.c` | 真实 `rand16seed`（`random8()` 的状态） |

## 2. 运行

```bash
./harness --frames 120 --dt-ms 68 --out led_frames.json
./harness --frames 120 --dt-ms 68 --out -            # JSON 到 stdout，统计到 stderr
./harness --list-modes                               # 打印固件的 mode 编号表
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--frames N` | 120 | 每个灯效输出多少帧 |
| `--dt-ms N` | 68 | 每帧推进多少虚拟毫秒（即 `g_rgb_timer += N`） |
| `--out PATH` | `led_frames.json` | `-` 表示 stdout |
| `--speed N` | 16 | `rgb_matrix_config.speed`（固件 `RGB_MATRIX_DEFAULT_SPD`） |
| `--hue/--sat/--val N` | 0 / 255 / 127 | `rgb_matrix_config.hsv`（见 §6） |
| `--seed N` | 555 | 固定随机种子（见 §7） |
| `--no-cie` | 关 | 用 `hsv_to_rgb_nocie()` 取代 CIE1931 曲线（会偏离真机，见 §8.1） |
| `--list-modes` | | 打印 mode 编号后退出 |

## 3. 输出格式

```json
{
  "led_count": 58, "frames": 120, "dt_ms": 68, "speed": 16,
  "hsv": [0, 255, 127], "max_brightness": 127,
  "effects": [
    {"name": "cycle_out_in", "mode": 15, "frames": [ [[r,g,b], ...58 项...], ...120 帧... ]},
    ...
  ]
}
```

顺序与 `--list-modes`：`cycle_out_in(15)`, `hue_wave(26)`, `rainbow_beacon(20)`,
`digital_rain(30)`, `jellybean_raindrops(23)`, `pixel_flow(28)`,
`solid_reactive_multinexus(38)`, `typing_heatmap(29)`。

RGB 是灯效算出来的**原始值**：没有乘 `RGB_MATRIX_MAXIMUM_BRIGHTNESS`（真机也不乘，
亮度是通过 `hsv.v` 进入灯效计算的），也不做任何缩放/伽马。渲染脚本自己决定亮度。

`digital_rain` 是唯一不经过 `hsv_to_rgb()` 的灯效（它直接
`rgb_matrix_set_color(led, boost, max_intensity, boost)`），所以它的绿通道可以到
127；其它灯效经 CIE 曲线后最大通道是 47（`CIE1931_CURVE[127] == 47`，见 §8.1）。

## 4. 用到的真实源码

| 真实文件 | 怎么用 |
| --- | --- |
| `quantum/rgb_matrix/animations/runners/rgb_matrix_runners.inc` | `#include`，它再 include 6 个 `effect_runner_*.h` |
| `.../animations/cycle_out_in_anim.h` | `#define RGB_MATRIX_EFFECT(name)` + `#define RGB_MATRIX_CUSTOM_EFFECT_IMPLS` 后 include（与 `rgb_matrix.c:44-62` 完全相同的做法） |
| `.../animations/hue_wave_anim.h` | 同上 |
| `.../animations/rainbow_beacon_anim.h` | 同上 |
| `.../animations/digital_rain_anim.h` | 同上 |
| `.../animations/jellybean_raindrops_anim.h` | 同上 |
| `.../animations/pixel_flow_anim.h` | 同上（走 `generated/`，见 §9.1） |
| `.../animations/solid_reactive_nexus.h` | 同上（同时提供 `SOLID_REACTIVE_NEXUS` 与 `SOLID_REACTIVE_MULTINEXUS`） |
| `.../animations/typing_heatmap_anim.h` | 同上（含真实 `process_rgb_matrix_typing_heatmap()`） |
| `quantum/rgb_matrix/animations/rgb_matrix_effects.inc` | 只用来**生成 mode 枚举**（`RGB_MATRIX_EFFECT(name,...)` → `RGB_MATRIX_##name,`），所以 mode 编号就是固件的编号 |
| `quantum/color.c` / `color.h` | 真实 `hsv_to_rgb`、`hsv_to_rgb_nocie` |
| `quantum/led_tables.c` / `.h` | 真实 `CIE1931_CURVE` |
| `lib/lib8tion/*`（`lib8tion.h`, `math8.h`, `scale8.h`, `random8.h`, `trig8.h`） | 真实 8bit 数学；`trig8.h` 走 `generated/`（见 §9.2） |
| `lib/lib8tion/lib8tion.c` | 真实 `rand16seed` 定义 |
| `quantum/rgb_matrix/rgb_matrix_types.h` | 真实 `led_config_t` / `effect_params_t` / `rgb_config_t` / `last_hit_t` / `LED_FLAG_*` / `NO_LED` |
| `quantum/rgb_matrix/post_config.h` | **直接 include**：由 `ENABLE_RGB_MATRIX_*` 真实推导出 `RGB_MATRIX_FRAMEBUFFER_EFFECTS` / `RGB_MATRIX_KEYPRESSES` |
| `quantum/compiler_support.h`, `quantum/util.h`, `quantum/color.h`, `quantum/bits.h`, `quantum/bitwise.h`, `platforms/progmem.h` | 真实头文件（非 AVR 时 `progmem.h` 就是普通内存） |

## 5. 框架桩：从 `quantum/rgb_matrix/rgb_matrix.c` 抄了什么

| harness 里的东西 | 出处 | 改动 |
| --- | --- | --- |
| `k_rgb_matrix_center = {112, 32}` | `rgb_matrix.c:31-35` | 无（`RGB_MATRIX_CENTER` 未定义，固件也是这个值） |
| `rgb_config_t rgb_matrix_config; uint32_t g_rgb_timer;` | `rgb_matrix.c:66-67` | 无 |
| `uint8_t g_rgb_frame_buffer[MATRIX_ROWS][MATRIX_COLS]` | `rgb_matrix.c:68-70` | 无 |
| `last_hit_t g_last_hit_tracker;` + 内部双缓冲 `last_hit_buffer` | `rgb_matrix.c:71-73, 90-93` | **双缓冲照抄**（见 §6） |
| `rgb_matrix_hsv_to_rgb()` | `rgb_matrix.c:37-39` | 唯一改动：按 `--no-cie` 选 `hsv_to_rgb`/`hsv_to_rgb_nocie`（默认与固件一致） |
| `rgb_matrix_map_row_column_to_led{,_kb}()` | `rgb_matrix.c:141-153` | 无（`_kb` 与 `default_keyboard.c:48-50` 一样返回 0） |
| `rgb_matrix_set_color()` / `_all()` | `rgb_matrix.c:179-195` | 去掉 `rgb_matrix_led_index()`（split 归属判断），直接写内部缓冲；等价于 `ws2812_vendor.c:271-284` 的 driver 行为 |
| `rgb_matrix_handle_key_event()` | `rgb_matrix.c:197-245` | 去掉 `if (!is_keyboard_master()) return;`（见 §8.2）；其余逐行照抄，含 `last_hit_buffer` 的 `memmove` 与 heatmap 调用条件 `mode == RGB_MATRIX_TYPING_HEATMAP` |
| `rgb_matrix_get_limits()` | `rgb_matrix.c:455-481` | 取 `#else` 分支（`{0, RGB_MATRIX_LED_COUNT}`，见 §8.3） |
| `rgb_matrix_check_finished_leds()` | `rgb_matrix.h:283-293` | 去掉 `RGB_MATRIX_SPLIT` 分支后即 `led_idx < RGB_MATRIX_LED_COUNT` |
| `rgb_task_timers()`（tick 递推） | `rgb_matrix.c:280-297` | 照抄，含 `UINT16_MAX - deltaTime < tick` 溢出丢弃与 `count--`；`deltaTime` 由 harness 传 `dt_ms` |
| `rgb_task_start()` | `rgb_matrix.c:305-328` | 去掉 suspend / timeout / EEPROM 分支；`g_last_hit_tracker = last_hit_buffer` 照抄 |
| `rgb_task_render()` | `rgb_matrix.c:330-397` | 照抄，switch 只列这 8 个灯效；`init` 由 `rgb_last_effect`/`rgb_last_enable` 计算 |
| `rgb_task_flush()` | `rgb_matrix.c:399-409` | 照抄（“刷新驱动”这一步 = harness 把缓冲快照成一帧） |
| `rgb_matrix_init()` 里的 tracker 初始化 | `rgb_matrix.c:506-519` | 照抄（每个灯效开跑前重置，等价于刚开机） |
| `process_rgb_matrix_typing_heatmap()` | `typing_heatmap_anim.h:20-52` | 真实实现，未改 |

`RGB_MATRIX_USE_LIMITS()` / `RGB_MATRIX_TEST_LED_FLAGS()` /
`RGB_MATRIX_INDICATOR_SET_COLOR()` 等宏从 `rgb_matrix.h:100-115` 抠出来放进
`qmk_host.h`（只抠宏，不 include 那个头文件，避免把 `keyboard.h` /
`rgb_matrix_drivers.h` / chibios 拖进来）。

## 6. `rgb_matrix_config` 初值 与 帧推进方式

真机上这些值来自 EEPROM（出厂默认由 `eeconfig_update_rgb_matrix_default()` 写入，
`rgb_matrix.c:106-114`）。harness 用编译期默认值，每个灯效开跑前重置一次：

| 字段 | 值 | 来源 |
| --- | --- | --- |
| `enable` | `1` | `RGB_MATRIX_DEFAULT_ON` |
| `mode` | 该灯效自己的 mode | 8 个灯效各跑一轮 |
| `hsv` | `{0, 255, 127}` | `RGB_MATRIX_DEFAULT_HUE/SAT/VAL`；`VAL = RGB_MATRIX_MAXIMUM_BRIGHTNESS = 127`（`rgb_matrix.h:73-75` + `info_config.h:37`） |
| `speed` | `16` | `RGB_MATRIX_DEFAULT_SPD`（`info_config.h:49`） |
| `flags` | `0xFF` | `RGB_MATRIX_DEFAULT_FLAGS = LED_FLAG_ALL` |

`keyboards/sofle_pico/keymaps/default/keymap.c:793-797` 的 `fx_select()`（那 8 个灯效
直达键）也只做 `rgb_matrix_enable_noeeprom()` + `rgb_matrix_mode_noeeprom(mode)`，
不改 hsv/speed，所以上面的初值就是按下这些快捷键后灯效实际看到的值。

**每帧顺序**（默认 `dt_ms = 68`）：

1. 注入打字事件（见 §7）——`rgb_matrix_handle_key_event()`，命中项 tick 记 0；
2. `rgb_task_timers(dt_ms)`：虚拟时钟 `rgb_timer_buffer += dt_ms`，并把
   `last_hit_buffer.tick[]` 全部 `+= dt_ms`（溢出则丢弃该项）；
3. `rgb_task_start()`：`g_rgb_timer = rgb_timer_buffer`，
   `g_last_hit_tracker = last_hit_buffer`（双缓冲），`rgb_current_effect = mode`；
4. `rgb_task_render()`：`iter = 0`、`flags = 0xFF`、
   `init = (effect != rgb_last_effect)`（即每个灯效的**第 1 帧** `init = true`，之后 false）；
5. `rgb_task_flush()`：把内部 58 项缓冲快照成本帧；
6. 所以第 f 帧的 `g_rgb_timer == (f+1) * dt_ms`，120 帧覆盖 0 → 8160 ms。

真机上 `rgb_matrix_task()` 每 ~1 ms 被调一次、渲染节流 16 ms
（`RGB_MATRIX_LED_FLUSH_LIMIT`）；harness 直接在帧边界上做一次完整
`STARTING → RENDERING → FLUSHING`，**没有模拟 16 ms 节流**（默认 `dt_ms = 68 > 16`，
真机同样每帧渲染一次；若把 `dt_ms` 设成小于 16，真机会合并帧而 harness 不会）。

## 7. 打字事件脚本

固定序列（不用随机数），8 个灯效**共用同一套**：

* 第 0 帧不动（那一帧是 `params->init`，`digital_rain` / `typing_heatmap` 会清空
  `g_rgb_frame_buffer`）；
* 从第 1 帧开始，每 3 帧 `pressed=true`，下一帧同键 `pressed=false`；
* 因为固件定义的是 `RGB_MATRIX_KEYPRESSES`（不是 `_KEYRELEASES`），
  `pressed=false` 在 `rgb_matrix_handle_key_event()` 里是空操作——与真机一致。

序列（home row 为主、左右手严格交替、覆盖两半；列序：0=小指 … 5=内侧，
左手 home row 是 matrix row 1，右手是 row 6）：

```
(1,0) (6,3)   a / j        (1,1) (6,4)   s / k
(1,2) (6,2)   d / l        (1,3) (6,1)   f / ;
(0,2) (5,3)   e / u        (2,3) (7,3)   v / m
(1,4) (6,5)   g / h        (0,1) (5,4)   w / i
```

随机性只用于 `digital_rain`（`rand()/RAND_MAX`）和 `jellybean_raindrops` /
`pixel_flow`（`random8()`）。两个发生器在每个灯效开跑前都用同一个种子重置：
`srand(555)` + `random16_set_seed(555)`，所以 8 个灯效共享同一条随机流，多次运行
结果完全一致（除了 `--seed`）。种子 555 是挑出来的：`digital_rain` 每次新建雨滴
只有 `1/24` 概率，种子选不好整套动画会全黑。

## 8. 与真机的已知差异（诚实清单）

### 8.1 亮度 / CIE 曲线：**已对齐真机**
固件编译时带 `-DUSE_CIE1931_CURVE`（见 `.build/obj_sofle_pico_default/cflags.txt`），
所以真机的 `hsv_to_rgb()` 会把 value 通道过一遍 `CIE1931_CURVE[256]`。harness 同样
定义了它并使用真实曲线表，因此 `hsv.v = 127` 时最大通道是 `CIE1931_CURVE[127] = 47`
——这是真机 LED 实际拿到的值。`--no-cie` 换成 `hsv_to_rgb_nocie()` 得到 127（更亮，
但**不是**真机行为），只作为渲染时的备选。

同时对齐了固件 `cflags.txt` 里的 `-DFASTLED_SCALE8_FIXED=1`
（`scale8()/scale16by8()/scale16()` 的取整方式）和 `-DFASTLED_BLEND_FIXED=1`。
不加这两个，几乎每个灯效都会差 ±1。

### 8.2 不定义 `RGB_MATRIX_SPLIT`（一次算 58 颗）
固件是分体键盘，`RGB_MATRIX_SPLIT {29,29}`，左右两半各自跑一遍 29 颗。
harness 故意 `#undef RGB_MATRIX_SPLIT`，一个进程算全部 58 颗，并且因此不编译
`rgb_matrix_led_index()` / `is_keyboard_left()` / `is_keyboard_master()`。

* `rgb_matrix_handle_key_event()` 里 `if (!is_keyboard_master()) return;` 这一句
  在真机的 split 构建里同样**不会**被编译（它挂在 `#ifndef RGB_MATRIX_SPLIT` 下），
  所以去掉它才是忠实的。
* 对 **6/8 个灯效**（`cycle_out_in`、`hue_wave`、`rainbow_beacon`、`digital_rain`、
  `solid_reactive_multinexus`、`typing_heatmap`）结果与真机逐字节等价：前三个是
  逐灯无状态函数，`digital_rain` 每帧设置全部 58 颗且只跑一次迭代，
  `typing_heatmap` 每颗灯每帧最多处理一次，reactive 只读 `g_last_hit_tracker`。
* 对 **`jellybean_raindrops` 和 `pixel_flow`** 不等价：两者内部有**跨帧状态**，而
  split 固件里左右两半各有一份。`pixel_flow` 的 `static rgb_t led[58]` 在左半边只
  在 `[0,29)` 内移位、右半边在 `[0,58)` 内移位（只渲染 `[29,58)`）；
  `jellybean_raindrops` 的 `random8_max(58)` 索引在每半边只有一半概率落在自己的
  29 颗里。视觉风格一致，但“某一帧哪颗灯变色”不与 split 真机逐帧相同。
  （等价于一板不定义 `RGB_MATRIX_SPLIT` 的 58 颗键盘。）

### 8.3 `RGB_MATRIX_LED_PROCESS_LIMIT` 固定为 58（一次跑完全部 LED）
固件没定义它，`rgb_matrix.h:89-91` 默认 `(58+4)/5 = 12`，于是真机分 5 个 `iter`
（每次 12 颗）渲染一帧。harness 把它固定成 58，于是 `rgb_matrix_get_limits()` 走
`rgb_matrix.c` 的 `#else` 分支、恒返回 `{0, 58}`，`params->iter` 恒为 0。
对这 8 个灯效，每帧净结果与 5 段渲染相同（`jellybean` 的 `iter==0` 触发、
`typing_heatmap` 的 `iter==0` 计时器在真机每帧也只各触发一次）。**若哪天要加别的
灯效，这个假设需要重新检查。**

### 8.4 没有模拟 16 ms 渲染节流
见 §6。默认 `dt_ms = 68` 时无影响。

### 8.5 `rand()` 是宿主 libc 的，不是 newlib 的
`digital_rain` 用 `rand() < RAND_MAX/24` 决定要不要新建雨滴。固件跑的是
arm-none-eabi newlib 的 `rand()`，序列与 macOS libc 不同，所以**具体哪一列、
哪一帧掉雨滴与真机不同**（统计特性一致，且 harness 内部完全可复现）。

### 8.6 其它
* 按键事件是脚本注入的合成序列，不是真人打字。
* `rgb_matrix_indicators()` / `rgb_matrix_indicators_advanced()` 没有调用。
  这个键盘的 keymap 和 keyboard 目录都没有实现 `rgb_matrix_indicators_user` /
  `_advanced_user` / `rgb_matrix_set_color`，所以真机也没有额外覆盖层，
  这一项实际没有差异。
* 没有 suspend / RGB_MATRIX_TIMEOUT / EEPROM / VIA 影响。
* `eeconfig` 初值用的是编译期默认值；真机若 EEPROM 里存过别的 hsv/speed/mode，
  真机行为会不同（`--hue/--sat/--val/--speed` 可以复现）。

## 9. macOS / clang 的两处必要处理

Apple clang 和固件用的 arm-none-eabi-gcc 有两个不兼容点。`prepare_effects.py`
把**真实源文件**机械地复制到 `generated/`，并**在写文件前验证改动是“纯搬移/纯包裹”**，
验证不过就直接报错退出（不会静默产出错误代码）：

1. **`pixel_flow_anim.h` 的 GCC 嵌套函数**
   ```c
   static bool PIXEL_FLOW(effect_params_t* params) {
       inline uint32_t interval(void) { ... }   // clang: function definition is not allowed here
   ```
   处理：把 `inline uint32_t interval(void)` 原样提升为文件作用域的
   `static uint32_t interval(void)`，调用点不变（它没有捕获任何局部变量）。
   验证方式：忽略空白、把 `inline`→`static` 归一化后，两个版本的字符多重集必须完全
   相等（纯搬移）。
2. **`lib/lib8tion/trig8.h` 的 AVR 内联汇编**
   `sin8_avr()` 用了 AVR 专用寄存器约束 `"=d"`；clang 在语义分析阶段就校验 asm
   约束，即使这个函数在非 AVR 上根本是死代码，也会直接编译失败。
   处理：给它的定义包一层 `#if defined(__AVR__)`（该文件对
   `#define sin8 sin8_avr` 本来就用了同样的条件）。验证方式：全文件里 `sin8_avr`
   除定义外只出现在那一个 `#define` 上，且该 `#define` 确实位于
   `#if defined(__AVR__)` 块内；同时校验是纯插入。
   `qmk_host.h` 先 include `generated/trig8.h`（它定义了 `trig8.h` 的 include
   guard，于是 `lib8tion.h` 里那次 include 自动落空），并因此需要提前定义
   `LIB8STATIC` / `LIB8STATIC_ALWAYS_INLINE`（与 `lib8tion.h:170-171` 相同）。

`python3 prepare_effects.py --show-diff` 可以查看这两处改动的完整 diff，
`--check` 只验证不写文件。

## 10. 验证

```bash
bash build.sh                     # 0 error；1 个 warning（来自 QMK 自己的代码，见下）
./harness --frames 120 --dt-ms 68 --out led_frames.json
python3 -c "import json;d=json.load(open('led_frames.json'));print(d['led_count'],len(d['effects']))"
# -> 58 8
```

唯一的编译 warning：

```
quantum/rgb_matrix/animations/typing_heatmap_anim.h:79:49: warning:
  use of logical '&&' with constant operand [-Wconstant-logical-operand]
      for (uint8_t col = 0; col < MATRIX_COLS && RGB_MATRIX_LED_PROCESS_LIMIT; col++) {
```

这是 QMK 自己的代码（那个 `&&` 恒为真，真机 gcc 不报），没有改动它。

`./harness` 跑完会在 stderr 打印每个灯效的 `max_ch` / `frames!=f0` / `nonzero_fr` /
`lit_leds`。当前结果（120 帧、68 ms、seed 555、CIE 开）：

```
effect                      mode   max_ch     frames!=f0 nonzero_fr  lit_leds
cycle_out_in                  15       47            118        120      6960
hue_wave                      26       47            119        120      6960
rainbow_beacon                20       47            119        120      6960
digital_rain                  30      127             91        120       810
jellybean_raindrops           23       47            117        120      6960
pixel_flow                    28       47             97        120      3965
solid_reactive_multinexus     38       47            119        119      4018
typing_heatmap                29       47            119        119      4243
```

结构自检（不是只有“能解析”，而是检查灯效数学确实生效）：

* `cycle_out_in`：把 58 颗灯按到中心 `(112,32)` 的距离分组（27 组），**每组颜色必须
  只有一个值** —— 0 组违规（`CYCLE_OUT_IN_math` 只依赖 dist）。
* `hue_wave`：按 x 坐标分组，**每个 x 列颜色只有一个值** —— 0 列违规。
* `typing_heatmap` 第 1 帧：注入的是 `(row1,col0)` → LED 27 `(0,21)`；
  该帧亮起的 10 颗灯全部落在 `(0,21)` 半径 40 px 内。
* `digital_rain`：写的是原始绿通道，出现 `[95,127,95]`
  （`boost = max_brightness_boost = 95`，`green = max_intensity = 127`）。
* `jellybean_raindrops`：出现 82 种不同颜色（随机色相）。

`-fsanitize=address,undefined` 下跑 120 帧无任何报告。

## 11. 重新生成

```bash
# 1) LED 表（从已编译产物抽取，永远不要手抄）
python3 extract_led_config.py                 # -> led_config_gen.h
# 2) clang 兼容副本（纯搬移/纯包裹，带验证）
python3 prepare_effects.py                    # -> generated/
# 3) 编译 + 跑
bash build.sh && ./harness --frames 120 --dt-ms 68 --out led_frames.json
```

`led_config_gen.h` 由
`.build/obj_sofle_pico_default/src/default_keyboard.c` 里的 `g_led_config`
初始化列表**逐字节**抽出（脚本会校验 `matrix_co` 是 10×6、`point`/`flags` 各 58 项，
不符就报错退出），所以 LED 坐标、matrix→LED 映射、flags 不可能与固件不一致。

`info_config.h` 也是直接 `#include` 已编译产物的那一份，因此
`RGB_MATRIX_LED_COUNT`、`MATRIX_ROWS/COLS`、`RGB_MATRIX_MAXIMUM_BRIGHTNESS`、
`RGB_MATRIX_DEFAULT_SPD`、41 个 `ENABLE_RGB_MATRIX_*` 都来自固件本身。
（唯一被刻意 `#undef` 的是 `RGB_MATRIX_SPLIT`，理由见 §8.2。）

## 12. 本目录里的 `fx_*.gif` 不是采集器生成的

它们是上一级的 `gen_led_effects.py` 读 `led_frames.json` 画出来的演示动画
（8 个灯效各一段，整段共用 32 色调色板、每 2 帧取 1 帧），并会一并生成网页播放器要的
`../led_effects.js`。命令与说明见上一级 `README.md` 的 4.7 节：

```bash
cd .. && python3 gen_led_effects.py && python3 gen_index.py
```

其中 `fx_solid_white.gif`（纯白常亮，出厂默认）**不是采集器跑出来的**：它是常量输出——
`solid_color` 灯效 + 饱和 0 时 `hsv_to_rgb()` 直接走 `rgb.r = rgb.g = rgb.b = CIE1931_CURVE[hsv.v]`
这一支，127 查表得 47，所以 58 颗灯都是 `RGB(47,47,47)`，`gen_led_effects.py` 直接算这一帧
（只有 1 帧，静态）。其余 8 个都是本采集器逐帧跑出来的。

想更亮（不过 CIE 曲线）可以 `./harness --no-cie --out /tmp/frames_bright.json`，
再用 `gen_led_effects.py` 指过去重新画——但默认这一份是**和真机一致**的（见 §8.1）。
