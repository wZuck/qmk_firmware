#!/usr/bin/env bash
#
# Build the sofle_pico RGB Matrix harness as a native macOS binary.
#
#   bash build.sh            # -> ./harness
#   bash build.sh --clean
#
# The compile step pulls in REAL QMK sources:
#   quantum/color.c                      (hsv_to_rgb)
#   lib/lib8tion/lib8tion.c              (rand16seed)
#   the eight effect headers, the six effect runners and
#   quantum/rgb_matrix/animations/rgb_matrix_effects.inc (via harness.c)
# Nothing in this directory re-implements an effect.
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

ROOT="$(cd ../.. && pwd)"                 # qmk_firmware checkout
BUILD_DIR="$ROOT/.build/obj_sofle_pico_default/src"
OUT="${OUT:-harness}"

if [ "${1:-}" = "--clean" ]; then
    rm -f "$OUT"
    rm -rf generated
    echo "cleaned"
    exit 0
fi

CC="${CC:-cc}"
if ! command -v "$CC" >/dev/null 2>&1; then
    echo "build.sh: compiler '$CC' not found" >&2
    exit 1
fi

# Keep the extracted LED table in sync with the firmware artifact.
if [ ! -f "$BUILD_DIR/default_keyboard.c" ]; then
    echo "build.sh: $BUILD_DIR/default_keyboard.c missing -- the sofle_pico firmware" >&2
    echo "          must be built once (this script never runs qmk)." >&2
    exit 1
fi
python3 extract_led_config.py >/dev/null

# generated/pixel_flow_anim.h holds the *same* QMK source with one GCC nested
# function hoisted to file scope; Apple clang rejects nested functions.  The
# script refuses to write the file unless the change is a pure move.
python3 prepare_effects.py

# Defines that the firmware build itself uses and that change effect output.
# Taken from .build/obj_sofle_pico_default/cflags.txt (do not guess these):
#   USE_CIE1931_CURVE   -> quantum/color.c runs hsv.v through the CIE1931 curve
#   FASTLED_SCALE8_FIXED -> lib8tion scale8()/scale16by8()/scale16() rounding
#   FASTLED_BLEND_FIXED  -> lib8tion blend8() rounding
FW_DEFINES=(
    -DUSE_CIE1931_CURVE
    -DFASTLED_SCALE8_FIXED=1
    -DFASTLED_BLEND_FIXED=1
)

CFLAGS=(
    -std=gnu11
    -O2
    -Wall
    -Wextra
    # QMK code is written for GCC/ARM and its own warning policy; keep the
    # noise down on the parts we do not own.
    -Wno-unused-parameter
    -Wno-unused-function
    -Wno-unused-variable
    -Wno-unused-but-set-variable
    -Wno-sign-compare
    -Wno-missing-field-initializers
)
INCLUDES=(
    -I"$PWD"                                    # qmk_host.h, led_config_gen.h, generated/
    -I"$ROOT"                                   # repository root
    -I"$ROOT/quantum"                           # color.h, util.h, bits.h, bitwise.h
    -I"$ROOT/lib"                               # lib8tion.h
    -I"$ROOT/lib/lib8tion"
    -I"$ROOT/platforms"                         # progmem.h (host build: plain memory)
    -I"$ROOT/quantum/rgb_matrix"                # rgb_matrix_effects.inc, runners.inc
    -I"$ROOT/quantum/rgb_matrix/animations"     # the effect headers
    -I"$ROOT/quantum/rgb_matrix/animations/runners"  # effect_runner_*.h
    -I"$BUILD_DIR"                              # info_config.h (real compiled config)
)

set -x
"$CC" "${CFLAGS[@]}" "${FW_DEFINES[@]}" "${INCLUDES[@]}" \
    harness.c \
    "$ROOT/quantum/color.c" \
    "$ROOT/quantum/led_tables.c" \
    "$ROOT/lib/lib8tion/lib8tion.c" \
    -o "$OUT"
set +x

echo
echo "built ./$OUT"
"$OUT" --help >/dev/null 2>&1 || true
