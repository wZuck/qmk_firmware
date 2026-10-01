#!/usr/bin/env python3
"""Prepare host (Apple clang) compatible copies of QMK sources.

The harness must compile the *real* QMK effect sources, but three pieces of the
repository are written for the firmware toolchains (arm-none-eabi-gcc / AVR gcc)
and are not acceptable to Apple clang:

  1. quantum/rgb_matrix/animations/pixel_flow_anim.h
     defines a block-scope (GCC "nested") function, which clang rejects with
     "function definition is not allowed here".

  2. lib/lib8tion/trig8.h
     defines `sin8_avr()`, whose body is AVR inline assembly with the AVR-only
     register constraint "=d"; clang validates asm constraints eagerly, even in
     code that is dead on this target, and fails on arm64.

For each of them this script writes a copy into `generated/` and *verifies*
that the change is exactly the documented one and nothing else:

  * pixel_flow_anim.h -> the nested `interval()` definition is moved verbatim to
    file scope as `static` (a pure move; verified by whitespace-stripped
    character multiset equality, with `inline` -> `static` normalised).
    The call site is untouched and `interval()` closes over no locals.

  * trig8.h -> `sin8_avr()` is wrapped in `#if defined(__AVR__)`, which is what
    the file already does for `#define sin8 sin8_avr`.  This is verified by
    checking that the only other reference to the symbol in the whole file is
    that `#define`, and that it sits inside an `#if defined(__AVR__)` region.
    Nothing outside the AVR path can therefore change.

No effect algorithm is re-implemented anywhere.

Usage:
    python3 prepare_effects.py            # (re)generate generated/
    python3 prepare_effects.py --check    # verify only, write nothing
    python3 prepare_effects.py --show-diff
"""

from __future__ import annotations

import argparse
from collections import Counter
import difflib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
GENERATED_DIR = HERE / "generated"

BANNER = """/* AUTO-GENERATED -- DO NOT EDIT.
 *
 * Host-compatible copy of
 *   {source}
 * produced by build_soflepico/led_effects/prepare_effects.py.
 *
 * Change applied:
 *   {note}
 *
 * Run `python3 prepare_effects.py --show-diff` to see the exact difference, and
 * `--check` to re-verify it against the current QMK sources.
 */

"""


# ---------------------------------------------------------------------------
# fix 1: GCC nested function -> file scope
# ---------------------------------------------------------------------------

NESTED_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]+)inline[ \t]+(?P<ret>[A-Za-z_][A-Za-z0-9_ \t*]*?)[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*\(void\)[ \t]*\{\n"
    r"(?P<body>.*?)"
    r"^(?P=indent)\}\n",
    re.S,
)
FUNC_OPEN_RE = re.compile(r"(?m)^[A-Za-z_][A-Za-z0-9_ \t*]*\([^;{}\n]*\)[ \t]*\{[ \t]*$")


def fix_nested_function(text: str) -> tuple[str, str]:
    matches = list(NESTED_RE.finditer(text))
    if len(matches) != 1:
        raise SystemExit(f"error: expected exactly 1 block-scope function definition, found {len(matches)}")
    m = matches[0]
    if m.group("name") != "interval":
        raise SystemExit(f"error: unexpected nested function name {m.group('name')!r}")

    funcs = list(FUNC_OPEN_RE.finditer(text, 0, m.start()))
    if not funcs:
        raise SystemExit("error: could not find the enclosing function of the nested definition")
    enclosing = funcs[-1]

    hoisted = f"static {m.group('ret')} {m.group('name')}(void) {{\n{m.group('body')}}}\n\n"
    without = text[: m.start()] + text[m.end() :]
    new_text = without[: enclosing.start()] + hoisted + without[enclosing.start() :]

    # pure-move verification
    if m.group("body") not in hoisted:
        raise SystemExit("error: hoisted body differs from the nested body")
    sig_old = f"{m.group('indent')}inline {m.group('ret')} {m.group('name')}(void)"
    sig_new = f"static {m.group('ret')} {m.group('name')}(void)"
    before = Counter(re.sub(r"\s+", "", text.replace(sig_old, sig_new)))
    after = Counter(re.sub(r"\s+", "", new_text))
    if before != after:
        raise SystemExit(
            "error: not a pure move -- refusing to write.\n"
            f"       added: {dict(after - before)!r}\n"
            f"       removed: {dict(before - after)!r}"
        )
    line = text[: m.start()].count("\n") + 1
    return new_text, (
        f"the block-scope (GCC nested) function `{m.group('name')}()` on line {line} "
        f"(inside `{text[enclosing.start():enclosing.end()].strip()}`) was hoisted verbatim to file "
        f"scope as `static`; clang rejects nested function definitions. Pure move, verified."
    )


# ---------------------------------------------------------------------------
# fix 2: AVR-only function -> behind #if defined(__AVR__)
# ---------------------------------------------------------------------------

AVR_FUNC_TMPL = r"(?m)^{ret}[ \t]+{name}\([^)]*\)[ \t]*\n\{{.*?^\}}\n"


def enclosing_if_conditions(lines: list[str], idx: int) -> list[str]:
    """Return the conditions of the #if/#ifdef blocks enclosing lines[idx]."""
    stack: list[list[str]] = []
    for i in range(idx + 1):
        stripped = lines[i].lstrip()
        if re.match(r"#\s*(if|ifdef|ifndef)\b", stripped):
            stack.append([stripped])
        elif re.match(r"#\s*elif\b", stripped) and stack:
            stack[-1].append(stripped)
        elif re.match(r"#\s*else\b", stripped) and stack:
            stack[-1].append(stripped)
        elif re.match(r"#\s*endif\b", stripped) and stack:
            stack.pop()
    return [" / ".join(conds) for conds in stack]


def fix_avr_only_function(text: str) -> tuple[str, str]:
    name = "sin8_avr"
    pattern = re.compile(AVR_FUNC_TMPL.format(ret=re.escape("LIB8STATIC uint8_t"), name=name), re.S)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise SystemExit(f"error: expected exactly 1 definition of {name}(), found {len(matches)}")
    m = matches[0]

    # The function must be referenced nowhere else except the AVR-only
    # `#define sin8 sin8_avr` line.
    outside = text[: m.start()] + text[m.end() :]
    refs = [(i, l) for i, l in enumerate(outside.splitlines()) if name in l]
    if len(refs) != 1 or not re.match(r"\s*#\s*define\s+sin8\s+" + name + r"\s*$", refs[0][1]):
        raise SystemExit(f"error: unexpected references to {name}() outside its definition: {refs!r}")
    conds = enclosing_if_conditions(outside.splitlines(), refs[0][0])
    avr_cond = next((c for c in conds if "__AVR__" in c), None)
    if avr_cond is None:
        raise SystemExit(f"error: `#define sin8 {name}` is not inside an __AVR__ block (enclosing: {conds!r})")

    guard = "#if defined(__AVR__) /* host: added by prepare_effects.py -- AVR-only inline asm */\n"
    inserted = guard + m.group(0) + "#endif\n"
    new_text = text[: m.start()] + inserted + text[m.end() :]

    # pure-insertion verification: the wrapped text must appear exactly once and
    # unwrapping it must reproduce the original byte for byte
    if new_text.replace(inserted, m.group(0), 1) != text:
        raise SystemExit("error: not a pure insertion -- refusing to write")

    line = text[: m.start()].count("\n") + 1
    return new_text, (
        f"the AVR-only `{name}()` definition on line {line} was wrapped in `#if defined(__AVR__)`. "
        "It is AVR inline asm (register constraint \"=d\") that clang refuses to parse for arm64; "
        f"the only other reference to it, `#define sin8 {name}`, is already inside "
        f"`{avr_cond}`. Pure insertion, verified."
    )


FIXES = [
    (REPO_ROOT / "quantum" / "rgb_matrix" / "animations" / "pixel_flow_anim.h", "pixel_flow_anim.h", fix_nested_function),
    (REPO_ROOT / "lib" / "lib8tion" / "trig8.h", "trig8.h", fix_avr_only_function),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    ap.add_argument("--show-diff", action="store_true", help="print a unified diff for every fix")
    args = ap.parse_args()

    if not args.check:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    for source, dest_name, fix in FIXES:
        if not source.is_file():
            print(f"error: {source} not found", file=sys.stderr)
            return 1
        original = source.read_text(encoding="utf-8")
        fixed, note = fix(original)
        dest = GENERATED_DIR / dest_name

        if args.show_diff:
            sys.stdout.writelines(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    fixed.splitlines(keepends=True),
                    fromfile=str(source.relative_to(REPO_ROOT)),
                    tofile=str(dest.relative_to(REPO_ROOT)),
                )
            )

        if args.check:
            print(f"ok   {source.relative_to(REPO_ROOT)}: {note}")
        else:
            dest.write_text(BANNER.format(source=source.relative_to(REPO_ROOT), note=note) + fixed, encoding="utf-8")
            print(f"wrote {dest.relative_to(REPO_ROOT)}: {note}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
