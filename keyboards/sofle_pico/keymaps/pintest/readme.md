# sofle_pico `pintest` keymap (matrix pin self test)

Not for daily use. It exercises every matrix pin electrically and prints the
result over the USB console, so a bad pin can be found without a multimeter.

```
make sofle_pico:pintest
qmk console
```

Every 5 seconds it prints one block per half (the one with the USB cable):

```
--- sofle_pico pin test, this half is left ---
col0 GP1   up=1 down=0 low=0  OK
col1 GP2   up=1 down=0 low=0  OK
col2 GP3   up=0 down=0 low=1  BAD: line held low (short to GND, or dead pin)
...
no bridges between matrix pins
--- end ---
```

## What each column means

| field | test | expected | what a wrong value means |
|---|---|---|---|
| `up` | input with pull-up | 1 | 0 = something is holding the line low (short to GND, or the pin is dead) |
| `down` | input with pull-down | 0 | 1 = something is holding the line high (short to 3V3) |
| `low` | drive low, read back | 0 | 1 = the pin cannot sink current (dead pin), or is pulled high hard |

`BRIDGE: col1 GP2 <-> col3 GP4` means those two lines are connected to each
other (solder bridge, or a short on the PCB).

## The decisive test for a suspect Pico

1. If the Pico is in a socket, **pull it out of the keyboard** and plug it into
   USB on its own (nothing else attached), then flash `pintest` and watch the
   console. With nothing else connected, the only things that can pull a line
   are the pin itself and its solder joint.
   * still `BAD` -> the Pico (or its header solder joint) is the problem
   * everything `OK` -> the Pico is fine on its own; the fault is on the PCB or
     in the socket/headers
2. If it is soldered down, do the same with the **jumper test** in the `debug`
   keymap readme: short the pin at the Pico's own leg (not at the PCB pad) to
   GP9 and watch for `DOWN`. Working at the leg but not at the pad = solder
   joint.
