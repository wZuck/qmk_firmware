# 左手按键缺失的排查指南（怀疑 Pico / 板子）

症状（已由 `probe` 固件确认）：**左半只有矩阵列 4、5（GP5、GP8）在行 0-3 出键，列 0-3（GP1-GP4）整片不出**，
而拇指行的 GP4（LOWER）是好的、右手完全正常、`MO(1)`/`Enter` 都对。

固件侧已经排除的：`matrix_pins` 与上游 QMK 一致（行 GP9-GP13、列 GP1 GP2 GP3 GP4 GP5 GP8、COL2ROW）、
手性正确、键位正确、EEPROM 已自动重写。所以问题在**引脚 → 走线 → 按键**这条链上。

![左手矩阵排查图](matrix_map_left.svg)

![Pico 引脚对照](pico_pinout.svg)

（上图：哪个键是哪个矩阵位置、哪一列不通；下图：这些引脚在 Pico 的哪个物理位置上，测的时候对着找。）

---

## 第一步：跑引脚自检固件（不用万用表）

烧 [`sofle_pico_pintest.uf2`](sofle_pico_pintest.uf2)（源码 `keyboards/sofle_pico/keymaps/pintest/`），
`qmk console` 看输出，每 5 秒一轮：

```
--- sofle_pico pin test, this half is left ---
col0 GP1   up=1 down=0 low=0  OK
col1 GP2   up=1 down=0 low=0  OK
col2 GP3   up=0 down=0 low=1  BAD: line held low (short to GND, or dead pin)
...
no bridges between matrix pins
```

| 字段 | 含义 | 正常 | 异常说明 |
|---|---|---|---|
| `up` | 内部上拉读回 | 1 | 0 = 这条线被拉低（对 GND 短路 / 引脚坏） |
| `down` | 内部下拉读回 | 0 | 1 = 被拉高（对 3V3 短路） |
| `low` | 拉低后读回 | 0 | 1 = 引脚拉不下去（死脚 / 被强上拉） |
| `BRIDGE` | 一根拉低、其他读回 | 无 | 两根线短在一起（连锡 / 板上短路） |

**关键做法：把 Pico 从键盘上拔下来（插座式的话），只插 USB 单独跑这个固件。**
此时没有任何外部线路能拉这些引脚，剩下的只有引脚本身和它的焊点：

- 单独跑还是 `BAD` → **Pico（或它的排针焊点）有问题**
- 单独跑全 `OK` → Pico 是好的，故障在 PCB 走线 / 排母 / 二极管 / 开关

## 第二步：万用表交叉验证（Pico 单独）

| 测试 | 方法 | 正常 |
|---|---|---|
| 对 GND / 3V3 短路 | 断电，二极管档量 GP1↔GND、GP1↔3V3 | 一个方向 0.5-0.7V，反向不通；**0Ω = 坏** |
| 空载电平 | 只插 USB（跑默认固件），直流档量 GP1-GP5、GP8 对 GND | 列脚是带上拉的输入，都应 ~3.3V；某个脚 0V 或中间值 = 该脚异常 |
| 引脚驱动能力 | 用 `pintest` 的 `low=` 结果替代 | `low=0` |

（`pintest` 运行时会短暂改动引脚电平，量电压时换回默认固件或 `probe` 更准。）

## 第三步：区分"芯片坏"还是"焊点坏"

- **插座式 Pico**：拔下来单测 → 单测坏 = Pico 问题；单测好但装上去坏 = 排母接触 / 焊点
- **焊死的**：用 `debug` 固件 + `qmk console`，拿跳线把 Pico 的**引脚根部**（不是 PCB 焊盘）短接到 GP9：
  - 引脚根部能出 `DOWN r0 cX`、焊盘上不出 → 焊点虚焊
  - 引脚根部也不出 → 引脚本身坏
- 补焊：GP1 / GP2 / GP3 / GP4 / GP8 重新上锡（助焊剂 + 350°C，2 秒内），排针根部尤其注意

## 第四步：换 Pico 时注意

- 本固件是按 **RP2040** 编的（`keyboard.json` 里 `"processor": "RP2040"`）。换 **Pico 2（RP2350）**
  不能直接烧这个 uf2，需要按 RP2350 重新编（对应平台支持也要跟着换）。
- 最省事的验证：**把两半的 Pico 对调**。故障跟着 Pico 走 = Pico 问题；故障留在左板 = 板子问题。

## 第五步：别漏掉"看起来像 Pico 坏"的情况

- **供电**：劣质 USB 线 / 同一 USB 口带两个 Pico / 长了会掉压 → 先换线换口试
- **3V3 不稳**：量 Pico 的 3V3 脚，应在 3.25-3.35V；掉到 3.0V 以下会随机丢键
- **RST/BOOT 虚焊**、GND 没接好也会表现为随机丢键

---

## 相关文件

| 文件 | 用途 |
|---|---|
| `sofle_pico_pintest.uf2` | 引脚电气自检 + 桥接检查（本轮新增） |
| `sofle_pico_debug.uf2` | 原始矩阵打控制台（`DOWN r2 c4`），可做跳线测试 |
| `sofle_pico_probe.uf2` | 每键唯一字符，快速看哪些键通 |
| `sofle_pico_default*.uf2` | 正常固件（`split-left` / `split-right` 强制手性） |

重新编译：`qmk compile -kb sofle_pico -km pintest`（`probe` / `debug` 同理）。
