# sofle_pico `probe` keymap (diagnostic)

Not for daily use. Every matrix position types one unique character, so you can
tell which keys actually register, and which half the firmware thinks each half
is.

**Switch your input method to plain English (ABC) first** - an IME hides the raw
characters. Then open a text editor and press every key in turn.

| what you press | what should appear |
|---|---|
| left half, matrix rows 0-4 | lowercase `a`..`z`, then `1 2 3 4` |
| right half, matrix rows 5-9 | uppercase `A`..`Z`, then `5 6 7 8` |

(The right half's letters are sent as Shift+letter on purpose, so the case
alone tells you which half the firmware thinks a key came from.)

| 半边 / 行 | 列 1 | 列 2 | 列 3 | 列 4 | 列 5 | 列 6 |
|---|---|---|---|---|---|---|
| **左** 0 | a | b | c | d | e | f |
| **左** 1 | g | h | i | j | k | l |
| **左** 2 | m | n | o | p | q | r |
| **左** 3 | s | t | u | v | w | x |
| **左** 4 | y | z | 1 | 2 | 3 | 4 |
| **右** 5 | A | B | C | D | E | F |
| **右** 6 | G | H | I | J | K | L |
| **右** 7 | M | N | O | P | Q | R |
| **右** 8 | S | T | U | V | W | X |
| **右** 9 | Y | Z | 5 | 6 | 7 | 8 |

Column 1 is the matrix column wired to GP1, column 2 to GP2, and so on:
GP1 GP2 GP3 GP4 GP5 GP8. Row 0 is GP9, row 1 GP10, row 2 GP11, row 3 GP12,
row 4 GP13, and the right half repeats the same pins, rows 5-9.

## How to read the result

* **A key types nothing** -> that matrix position is not registering. Look it up
  in the table and check that key's solder joint, its diode, and the row/column
  trace.
* **A whole row or column types nothing** -> the pin itself is the suspect
  (rows GP9-GP13, columns GP1 GP2 GP3 GP4 GP5 GP8). Reflow that pin on the Pico.
* **A key types the *wrong* character** -> the position it reports tells you
  where the firmware thinks it is: e.g. pressing `w` and getting `e` means the
  column is off by one (a bridge or a swapped trace).
* **Pressing the left half types uppercase** -> the halves have their handedness
  swapped (EE_HANDS lives in EEPROM). Flash the left half with
  `sofle_pico_default_split-left.uf2` and the right with `...split-right.uf2`.
* **A half works on its own (USB in it) but not through the split link** -> the
  link is the suspect, not the keys: the TRRS cable, or GP16/GP17.

Build/flash it with `qmk compile -kb sofle_pico -km probe`, or
`make sofle_pico:probe` to compile and flash in one go.
