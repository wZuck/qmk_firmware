![SofleKeyboard default keymap](https://github.com/josefadamcik/SofleKeyboard/raw/master/Images/soflekeyboard.png)
![SofleKeyboard adjust layer](https://github.com/josefadamcik/SofleKeyboard/raw/master/Images/soflekeyboard_layout_adjust.png)


# Default keymap for Sofle Pico Keyboard

Ported directly from the classic Sofle Keyboard by Josef Adamcik.
Layout in [Keyboard Layout Editor](http://www.keyboard-layout-editor.com/#/gists/76efb423a46cbbea75465cb468eef7ff) and [adjust layer](http://www.keyboard-layout-editor.com/#/gists/4bcf66f922cfd54da20ba04905d56bd4)


Features:

- Symmetric modifiers (CMD/Super, Alt/Opt, Ctrl, Shift)
- Modes for Mac vs Linux/Win support -> different order of modifiers and different action shortcuts on the "UPPER" layer (the red one in the image). Designed to simplify transtions when switching between operating systems often.
- Each half's OLED can show any of fourteen screens - status, stats, a WPM graph, the layer states,
  four mascot animations and their four inverted twins, and the snowboarding pair in both polarities
  (normal and inverted, i.e. night and day) - all cycled with the same `OLED` key on the adjust layer
  (hold it to auto-advance). Status on the left and `bounce` on the right by default.
- Screensaver: a minute with no key pressed on either half and *both* OLEDs show the sleeping mascot
  (the `sleep` loop, the one with the drifting z's); the first key press brings both back to their own
  screens. See the OLED section below.
- Left encoder: volume down/up, press mutes. Right encoder: previous/next track, press play/pause.
- `VIA_INSECURE` in this keymap's `config.h` lets VIA's Key Tester read the live matrix over raw
  HID; without it QMK answers that request with zeroes and the tester looks dead. It does mean any
  raw HID client can see which keys are down, so drop the line if that matters more than the tester.
- `SOFLE_EEPROM_VERSION` in `keymap.c`: VIA keeps the keymap in EEPROM and only seeds it from the
  firmware once, so on boot each half compares this number with what is stored and re-seeds the
  keymap (and encoder map) when it differs. Bump it whenever the layer structure or the keys move.
  `EE_CLR` on the adjust layer still clears the EEPROM by hand if needed.


## OLED

Each half runs the OLED task on its own, so nothing has to cross the split
link to draw a screen - but that also means each half decides what it shows.
Every half can cycle through the screens with its own `OLED` key on the adjust
layer (`OLED_NEXT` in `keymap.c`), in this order - holding the key down
auto-advances every 400 ms, so fourteen screens are not fourteen taps:

| # | screen | what it is |
|---|---|---|
| 1 | **status** | layer banner, mode, live modifiers, peak and current WPM with a bar, caps lock. Default on the left half. |
| 2 | **stats** | keys counted by this half, current and peak WPM, top active layer, uptime. |
| 3 | **graph** | current WPM in 2x digits plus the last 21 seconds as a bar chart (WPM is mirrored over the split, so both halves match). |
| 4 | **layers** | which of the four layers are on, which also shows the tri-layer bringing ADJUST up. |
| 5-8 | **anim 0..3** | the mascot loops in `oled_anim.h`: `bounce`, `wave`, `walk`, `sleep`. Eight frames each at 8 fps. Default on the right half (`anim 0`). |
| 9-12 | **anim inv 0..3** | the same four loops, every pixel flipped: dark mascot on a lit panel. The day counterpart of 5-8. |
| 13 | **snow** | the snowboarding pair, see below. |
| 14 | **snow inv** | the same pair, every pixel flipped. |

"Normal" and "inverted" are the same drawing at both polarities, for a dark
room and a bright one: normal draws lit strokes on a dark panel (the default
look), inverted flips every pixel so the panel is lit and the drawing is dark.
Nothing else differs - same frame clock, same speed.

### The snowboarding pair

Screens 13 and 14 show the two drawings from `oled_snow1.pdf` /
`oled_snow2.pdf`, downsized into `oled_snow.h` and alternating as a slow wave -
normal on 13, inverted on 14. There is no separate key for any of this: they
are simply the screens after the two mascot blocks in the `OLED` key's cycle.

The two drawings differ only in the left snowboarder's arm - down in one, up in
a peace sign in the other - which is what makes the pair an animation. They are
landscape drawings on a portrait panel: the crop is 64 px wide and keeps its
aspect (~62 px tall), centred on the canvas with blank bands above and below.
The frame clock always counts the mascot's 8 frames and the snow set wraps it,
so its two drawings get four ticks each and the wave runs at half the mascot's
rate.

`make_snow.py` regenerates `snow_1.png` / `snow_2.png` and their `_inv` twins
from the PDFs (standard library for reading them, Pillow for the image work);
`make_snow_header.py` then packs all four into `oled_snow.h`. Note that the
header stores a set bit for a *lit* pixel, matching `oled_anim.h` - `img2c.py`
alone would have packed the white background as lit, which is the opposite of
what these screens mean, so that step flips it.

The inverted mascot loops are generated too: `make_animations.py` writes
`oled_anim.h` and `oled_anim_inv.h` in one run, the second being the first with
every byte flipped - which is exactly flipping the pixels, since the buffer is
one bit per pixel either way.

The sleeping zzz screensaver stays the normal mascot whatever screen you left
up: the snow pair has no sleeping drawing, and a screensaver that inherited an
inversion would not look the same twice.

Because `process_record_user()` only runs on the master, a keycode cannot just
set a shared variable: the slave would never hear about it. Instead each half
watches its own matrix rows in `housekeeping_task_user()` and flips its own
screen, so one `OLED` key sits on each half and neither half needs to know
about the other. The choice lives in RAM, so a power cycle goes back to the
defaults.

Both halves are driven with the same rotation, giving each one a 64 px wide
x 128 px tall canvas: 16 text lines of 8 px.

```
   line  0  +----------------+
            |  ------------- |   rule
            |      LOWER     |   banner, lines 2-3, 12 x 16 px glyphs
            |  ------------- |   rule
            | MODE WIN       |   Mac / Win mode
            | MODS C..G      |   live modifiers: C S A G, '.' when not held
            | PEAK    88     |   best WPM of this typing burst
            | WPM    42      |
            | [---bar------] |
            |                |
            | CAPS OFF       |
   line 15  +----------------+
```

The animation also runs for `SOFLE_BOOT_MS` after power-up, on both halves,
before each half settles on the screen it has selected.

### Screensaver

Left alone, the keyboard falls asleep - both halves together: after
`SOFLE_SLEEP_MS` (a minute) with no key pressed on *either* half, the two OLEDs
show the sleeping mascot (`oled_anim.h`'s `sleep` loop, the one with the slowly
drifting z's), and the first key you press anywhere brings both back to
whatever screen each half was on. No key is swallowed on the way out: the press
that wakes the displays is the press you meant to make.

- **Sleeping is agreed, waking is local.** Each half counts hits on its own
  matrix rows in `housekeeping_task_user()`, the same place the `OLED` key is
  picked up, which is enough to *wake* instantly - any key on a half brings
  that half's display back within a scan, with no round trip to wait for. But
  it would also let one display sleep while you typed on the other, so falling
  asleep also needs the other half's answer: the master asks the slave "did you
  see a key this epoch?" over a split transaction (`SOFLE_SCREENSAVER_SYNC`,
  registered through `SPLIT_TRANSACTION_IDS_USER` in `config.h`) every
  `SOFLE_SLEEP_SYNC_MS` (250 ms), and a half only sleeps once neither half has
  seen anything for the full minute. Note the built-in
  `last_input_activity_elapsed()` would not do for either job: it is only
  touched on the master, so a slave half would sit asleep while you typed on it.
- **It is not a screen.** While asleep each half keeps the screen it was on in
  `oled_screen`, so falling asleep never costs you your chosen screen, and the
  `OLED` key still steps through the list underneath (its press wakes the
  display first).
- **It outranks the boot animation.** A keyboard left alone from power-up goes
  to sleep a minute in rather than hopping once and then freezing on a status
  screen.
- The animation clock (`oled_frame`) lives outside the renderer and runs on
  every OLED frame whatever is on screen, so the mascot breathes at
  `SOFLE_ANIM_FPS` while asleep and resumes the loop where it left off when
  you wake it.
- Timing is `SOFLE_SLEEP_MS`, the exchange period is `SOFLE_SLEEP_SYNC_MS` and
  the loop is `SOFLE_ANIM_SLEEP` - all near the top of the `OLED_ENABLE` block
  in `keymap.c`. Change the length there if a minute is not what you want.

`is_keyboard_left()` decides which half is which, and that comes from the
handedness in EEPROM - not from whichever half the USB cable is in. So the
left half may well be the slave, and the layer, LED and WPM state it shows
all have to be mirrored over the link. That is what the `SPLIT_*_ENABLE`
defines in this keymap's `config.h` are for.

Every string on the status screen is exactly nine characters, and is only
written with `oled_write_ln()`. That is not cosmetic: the font is fixed width
with 10 characters to a line, and `oled_advance_page()` pads the remainder one
character at a time. Nine characters leaves room for exactly one pad space,
which lands the cursor on the next line; ten would leave the cursor already
wrapped and make that pad wipe the line below.

### Replacing the right half

`oled_anim.h` is generated by **`make_animations.py`**, which draws every loop
of the big-eyed mascot: `bounce`, `wave`, `walk` and `sleep`, 8 frames
each. It is pure stdlib and writes the header next to itself:

```sh
cd keyboards/sofle_pico/keymaps/default
python3 make_animations.py
```

Add a loop by adding an entry to `ANIMATIONS` in that script - the `oled_screen`
range in `keymap.c` follows `SOFLE_ANIM_COUNT`, so nothing else needs touching -
then rebuild.

Each frame is the whole 64 x 128 canvas: 1024 bytes, 16 pages of 64 bytes,
where the least significant bit of a byte is the topmost of its 8 pixels. Edit
that script for your own art, or set `SOFLE_ANIM_FRAMES` to 1 to show a single
static picture.

### Drawing your own picture

Start from **`oled_template.png`** - a 64 x 128 black canvas at 4x (256 x 512
device pixels), so there is actually room to draw. The magenta lines mark the
8 px pages the driver writes in and the 16 px columns. They are hairlines,
deliberately thinner than one canvas pixel, so the 4:1 reduction averages them
away and they never reach the panel - draw over them or leave them, it makes no
difference.

`oled_template_1x.png` is the same canvas at 1:1 if you would rather work
pixel-exact. Both are generated by `make_template.py`.

When you are done, convert:

```sh
python3 img2c.py my_picture.png --height 128 --helper-color ff00ff -o my_picture.h
```

`img2c.py` scales any PNG, converts it to 1-bit and writes it out in the page
format the display wants - exactly the layout of one animation frame. There is
nothing to install; it is pure stdlib. It prints how many pixels ended up lit,
which is a quick sanity check that the picture survived the trip.

Useful flags:

| flag | what it does |
|---|---|
| `--height 128` | whole canvas, which is what an animation frame needs |
| `--height 96` | stop at 96 px, leaving the bottom 32 px free |
| `--fit contain` | letterbox (default) - `cover` crops to fill, `stretch` squashes |
| `--dither` | Floyd-Steinberg, keeps gradients readable; without it the image is hard-thresholded |
| `--threshold 128` | move the cutoff if the picture comes out too dark or too light |
| `--rotate 180` | turn the picture over, e.g. if it shows up upside down |
| `--invert` | swap black and white |
| `--helper-color ff00ff` | drop pixels of this colour. Worth adding with `--dither`: the leftover grid is only a little darker than the paper, and error diffusion turns that into a faint dotted line along every guide. At 4:1 without `--dither` the hairlines wash out on their own. |

`--height` has to be a multiple of 8.

### If a half comes out upside down

The two halves may want mirror-image rotations depending on how the panels are
soldered. Flip `SOFLE_OLED_ROTATION` in `keymap.c` between `OLED_ROTATION_90`
and `OLED_ROTATION_270` (they differ by 180 degrees) and rebuild.


