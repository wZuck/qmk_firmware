#!/usr/bin/env python3
"""从已编译的 ELF 里把 `keymaps` / `encoder_map` 抠出来，按层打印键码名字。

用途：VIA 把键位存在 EEPROM 里，改完 `keymap.c` 光看源码不放心，这个脚本读的是
**真正编进固件的那份表**（`.rodata` 里的 `keymaps` / `encoder_map`），改完 keymap.c
跑一下就知道有没有编进去、方向有没有反。

键码名字从 `quantum/keycodes.h` 的 `qk_keycode_defines` 枚举里解析（含别名和算术表达式），
`keymap.c` 里自定义的那几个（OLED_NEXT、FX_* …）从 `enum custom_keycodes` 里按顺序补上。

用法：
    python3 verify_keymap.py [.build/sofle_pico_default.elf]
"""

import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# QMK 自带的 ARM 工具链（没有 arm-none-eabi-* 前缀）
TOOLCHAIN = os.path.expanduser("~/Library/Application Support/qmk/arm-none-eabi/bin")

LAYER_NAMES = ["QWERTY", "LOWER", "RAISE", "ADJUST"]
MATRIX_ROWS, MATRIX_COLS = 10, 6
NUM_ENCODERS = 2

PREFERRED = ("XXXXXXX", "_______", "KC_TRANSPARENT", "KC_TRNS", "KC_NO")


# --------------------------------------------------------------------------
# 键码名字表
# --------------------------------------------------------------------------


def strip_comments(body):
    """注释里的逗号会打乱按逗号切分，先整块去掉。"""
    body = re.sub(r"/\*.*?\*/", " ", body, flags=re.S)
    return re.sub(r"//[^\n]*", " ", body)


def parse_keycode_names():
    """把 quantum/keycodes.h 的枚举解析成 {值: [名字, ...]}。"""
    text = open(os.path.join(ROOT, "quantum/keycodes.h"), encoding="utf-8").read()
    body = re.search(r"enum qk_keycode_defines\s*\{(.*?)\n\};", text, re.S).group(1)
    body = strip_comments(body)

    known = {}
    values = {}
    counter = 0
    for raw in body.split(","):
        item = raw.split("//")[0].strip()
        item = " ".join(l.strip() for l in item.splitlines() if not l.strip().startswith("#"))
        if not item:
            continue
        if "=" in item:
            name, expr = (p.strip() for p in item.split("=", 1))
            try:
                value = eval(re.sub(r"\b([A-Za-z_]\w*)\b", lambda m: str(known.get(m.group(1), m.group(1))), expr),
                             {"__builtins__": {}}, {})
                value = int(value)
            except Exception:
                continue
        else:
            name, value = item, counter
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            continue
        known[name] = value
        counter = value + 1
        values.setdefault(value & 0xFFFF, []).append(name)
    return values


def parse_custom_names(path):
    """keymap.c 里 enum custom_keycodes 的名字（第一个 = SAFE_RANGE = QK_USER）。"""
    text = open(path, encoding="utf-8").read()
    body = re.search(r"enum custom_keycodes\s*\{(.*?)\n\};", text, re.S).group(1)
    body = strip_comments(body)
    names, base = [], None
    for raw in body.split(","):
        item = " ".join(l.strip() for l in raw.splitlines()
                        if not l.strip().startswith("#")).strip()
        if not item:
            continue
        name, _, expr = item.partition("=")
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            continue
        if expr.strip() == "SAFE_RANGE":
            base = len(names)
        names.append(name)
    return names, (base or 0)


def name_of(value, names, custom, custom_base):
    if value in custom:
        return custom[value]
    for cand in PREFERRED:
        if cand in names.get(value, ()):
            return cand
    options = names.get(value)
    if not options:
        return f"?0x{value:04X}"
    return sorted(options, key=len)[0]


# --------------------------------------------------------------------------
# ELF
# --------------------------------------------------------------------------


def symbol(elf, name):
    out = subprocess.run([os.path.join(TOOLCHAIN, "nm"), "-S", elf],
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[3] == name:
            return int(parts[0], 16), int(parts[1], 16)
    raise SystemExit(f"ELF 里没有符号 {name}")


def read_bytes(elf, addr, size):
    out = subprocess.run([os.path.join(TOOLCHAIN, "objdump"), "-s",
                          f"--start-address={addr}", f"--stop-address={addr + size}", elf],
                         capture_output=True, text=True, check=True).stdout
    data = bytearray()
    for line in out.splitlines():
        m = re.match(r"\s*([0-9a-f]{4,})\s((?:[0-9a-f]{2,8}\s)+)", line)
        if m:
            data += bytes.fromhex("".join(m.group(2).split()))
    return bytes(data[:size])


def main():
    elf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, ".build/sofle_pico_default.elf")
    if not os.path.exists(elf):
        raise SystemExit(f"找不到 {elf}，先 qmk compile")

    names = parse_keycode_names()
    custom_names, custom_base = parse_custom_names(
        os.path.join(ROOT, "keyboards/sofle_pico/keymaps/default/keymap.c"))
    custom = {0x7E40 + custom_base + i: n for i, n in enumerate(custom_names)}

    addr, size = symbol(elf, "keymaps")
    keymaps = read_bytes(elf, addr, size)
    per_layer = MATRIX_ROWS * MATRIX_COLS * 2
    layers = size // per_layer
    print(f"{os.path.relpath(elf, ROOT)}：keymaps {size} 字节 = {layers} 层 × "
          f"{MATRIX_ROWS} 行 × {MATRIX_COLS} 列")

    for layer in range(layers):
        label = LAYER_NAMES[layer] if layer < len(LAYER_NAMES) else f"layer{layer}"
        print(f"\n=== 第 {layer} 层 {label} ===")
        for row in range(MATRIX_ROWS):
            off = layer * per_layer + row * MATRIX_COLS * 2
            codes = struct.unpack_from(f"<{MATRIX_COLS}H", keymaps, off)
            names_row = [name_of(c, names, custom, custom_base) for c in codes]
            side = "左" if row < MATRIX_ROWS // 2 else "右"
            # 右半的列在物理上是从 col5 到 col0（镜像），按屏幕顺序打出来更好读
            shown = list(reversed(names_row)) if side == "右" else names_row
            print(f"  r{row}({side}): " + " ".join(f"{n:<16}" for n in shown))

    addr, size = symbol(elf, "encoder_map")
    enc = read_bytes(elf, addr, size)
    print(f"\nencoder_map {size} 字节 = {size // 8} 层 × {NUM_ENCODERS} 个旋钮 × 2 个方向")
    for layer in range(size // 8):
        label = LAYER_NAMES[layer] if layer < len(LAYER_NAMES) else f"layer{layer}"
        left = struct.unpack_from("<2H", enc, layer * 8)
        right = struct.unpack_from("<2H", enc, layer * 8 + 4)
        fmt = lambda pair: (f"CW={name_of(pair[0], names, custom, custom_base):<12} "
                            f"CCW={name_of(pair[1], names, custom, custom_base):<12}")
        print(f"  {label:<7} 左旋钮 {fmt(left)} | 右旋钮 {fmt(right)}")


if __name__ == "__main__":
    main()
