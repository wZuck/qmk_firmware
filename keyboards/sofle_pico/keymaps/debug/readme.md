# sofle_pico `debug` keymap (raw matrix over the console)

Not for daily use. It prints every matrix edge over the USB console, so you can
tell "this key never reaches the firmware" apart from "this key reaches the
firmware but ends up as another character".

## Use

```
make sofle_pico:debug          # or: qmk compile -kb sofle_pico -km debug
qmk console                    # then press keys one at a time
```

A press/release pair looks like:

```
DOWN r2 c4
UP   r2 c4
```

Boot prints which half this firmware thinks it is (`... this half is left`).

## Why plug the USB into the half you are testing

Only the master sees the split link. With the cable in the half under test, the
rows you see are that half's own matrix - so a key that prints nothing there is
not a cable/link problem, the key or its row/column line is not reaching the
MCU.

## Reading it

* columns are `GP1 GP2 GP3 GP4 GP5 GP8` = `c0 c1 c2 c3 c4 c5`
* rows are `GP9 GP10 GP11 GP12 GP13` = `r0 r1 r2 r3 r4` (left) and `r5..r9` (right)
* rows `r5..r9` sit idle when the cable is in the left half - that is the slave,
  it has no link data to show here
* a key that prints **nothing at all** -> that matrix position is not making
  contact: switch, diode, or the row/column line
* a key that prints a **different position** than the one you pressed -> the
  firmware is reading the right matrix, the wiring is not where it is expected
* positions that go down **on their own** -> a shorted row/column, or a diode
  the wrong way round
