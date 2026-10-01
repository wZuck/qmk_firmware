#!/usr/bin/env python3
"""Extract the real `g_led_config` initialiser for sofle_pico out of QMK's
already-compiled build artifact and emit `led_config_gen.h`.

The data is taken verbatim from

    .build/obj_sofle_pico_default/src/default_keyboard.c

(which is the file the QMK build system generates from the keyboard's
`keyboard.json` / `<keyboard>.c`), so the harness can never disagree with the
firmware about LED positions, the matrix -> LED mapping or the LED flags.

Usage:
    python3 extract_led_config.py [--source PATH] [--out PATH]

Re-running it is always safe: the output is deterministic.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

DEFAULT_SOURCE = REPO_ROOT / ".build" / "obj_sofle_pico_default" / "src" / "default_keyboard.c"
DEFAULT_OUT = HERE / "led_config_gen.h"

# Sanity limits coming from the compiled firmware (info_config.h).
EXPECTED_LED_COUNT = 58
EXPECTED_MATRIX_ROWS = 10
EXPECTED_MATRIX_COLS = 6


def find_braced_block(text: str, start: int) -> tuple[str, int]:
    """Return (inner_text, index_after_closing_brace) for the `{...}` starting at
    or after `start`.  Braces inside strings/comments are not handled, but the
    generated file contains neither in this region."""
    open_idx = text.index("{", start)
    depth = 0
    for i in range(open_idx, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i], i + 1
    raise ValueError("unbalanced braces while looking for g_led_config initialiser")


def split_top_level(inner: str) -> list[str]:
    """Split the body of an initialiser into its top-level `{...}` groups."""
    groups: list[str] = []
    depth = 0
    start = None
    for i, c in enumerate(inner):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                groups.append(inner[start : i + 1])
                start = None
    if depth != 0:
        raise ValueError("unbalanced braces while splitting g_led_config initialiser")
    return groups


def count_leaf_values(group: str) -> list[str]:
    """Flatten all scalars inside a `{...}` group."""
    return re.findall(r"\{\s*([^{}]*?)\s*\}", group)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help=f"build artifact to read (default: {DEFAULT_SOURCE})")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"header to write (default: {DEFAULT_OUT})")
    args = ap.parse_args()

    source: Path = args.source
    if not source.is_file():
        print(f"error: {source} not found -- build sofle_pico first (do NOT run qmk compile from here)", file=sys.stderr)
        return 1

    text = source.read_text(encoding="utf-8")
    m = re.search(r"\bg_led_config\s*=\s*", text)
    if not m:
        print(f"error: no `g_led_config =` initialiser found in {source}", file=sys.stderr)
        return 1

    inner, _ = find_braced_block(text, m.end())
    groups = split_top_level(inner)
    if len(groups) != 3:
        print(f"error: expected 3 top-level groups (matrix_co, point, flags), got {len(groups)}", file=sys.stderr)
        return 1

    matrix_co_s, point_s, flags_s = groups

    matrix_rows = count_leaf_values(matrix_co_s)
    if len(matrix_rows) != EXPECTED_MATRIX_ROWS:
        print(f"error: matrix_co has {len(matrix_rows)} rows, expected {EXPECTED_MATRIX_ROWS}", file=sys.stderr)
        return 1
    for r, row in enumerate(matrix_rows):
        n = len([v for v in row.split(",") if v.strip()])
        if n != EXPECTED_MATRIX_COLS:
            print(f"error: matrix_co row {r} has {n} columns, expected {EXPECTED_MATRIX_COLS}", file=sys.stderr)
            return 1

    point_entries = [v for v in point_s.split("},") if v.strip()]
    if len(point_entries) != EXPECTED_LED_COUNT:
        # fall back to a stricter brace-balanced count
        point_entries = re.findall(r"\{[^{}]*\}", point_s)
    if len(point_entries) != EXPECTED_LED_COUNT:
        print(f"error: point[] has {len(point_entries)} entries, expected {EXPECTED_LED_COUNT}", file=sys.stderr)
        return 1

    flags = [v.strip() for v in flags_s.replace("{", "").replace("}", "").split(",") if v.strip()]
    if len(flags) != EXPECTED_LED_COUNT:
        print(f"error: flags[] has {len(flags)} entries, expected {EXPECTED_LED_COUNT}", file=sys.stderr)
        return 1

    # Re-emit with stable, pretty formatting: keep QMK's own row/entry layout.
    body = inner.strip("\n")

    digest = hashlib.sha256(inner.encode("utf-8")).hexdigest()[:16]

    header = f"""/* AUTO-GENERATED -- DO NOT EDIT BY HAND.
 *
 * `g_led_config` for sofle_pico, copied verbatim from
 *   {source.relative_to(REPO_ROOT)}
 * by build_soflepico/led_effects/extract_led_config.py
 *
 * Source blob sha256[:16]: {digest}
 * Counts verified: matrix_co {EXPECTED_MATRIX_ROWS}x{EXPECTED_MATRIX_COLS},
 *                  point[{EXPECTED_LED_COUNT}], flags[{EXPECTED_LED_COUNT}]
 *
 * Regenerate with:
 *   python3 build_soflepico/led_effects/extract_led_config.py
 *
 * Needs: MATRIX_ROWS, MATRIX_COLS, RGB_MATRIX_LED_COUNT and `led_config_t`
 * (from quantum/rgb_matrix/rgb_matrix_types.h) to be visible already.
 */

led_config_t g_led_config = {{
{body}
}};
"""

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header, encoding="utf-8")
    print(f"wrote {args.out.relative_to(REPO_ROOT)} ({len(header)} bytes, blob sha256[:16]={digest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
