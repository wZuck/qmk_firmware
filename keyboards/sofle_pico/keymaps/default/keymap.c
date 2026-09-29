// Copyright 2023 Ryan Neff (@JellyTitan)
// SPDX-License-Identifier: GPL-2.0-or-later

#include QMK_KEYBOARD_H
// Not pulled in by quantum.h, needed for keycode_at_keymap_location_raw()
#include "keymap_introspection.h"

enum sofle_layers {
    _QWERTY,
    _LOWER,
    _RAISE,
    _ADJUST,
};

enum custom_keycodes {
    /* Switches what *this* half's OLED shows; put one on each half so each
     * half has its own key. Handled in housekeeping_task_user(), see below. */
    OLED_NEXT = SAFE_RANGE,
    KC_PRVWD,
    KC_NXTWD,
    KC_LSTRT,
    KC_LEND,
    KC_DLINE
};

#ifdef OLED_ENABLE
// The animation library: SOFLE_ANIM_COUNT loops of SOFLE_ANIM_FRAMES frames.
#    include "oled_anim.h"

/* What each half draws. Every animation counts as its own screen, so the OLED
 * key walks status -> stats -> graph -> layers -> animation 0..N-1 -> logo ->
 * status, and holding it down auto-advances. The choice is per half and lives
 * in RAM only, so a power cycle goes back to the defaults set in
 * keyboard_post_init_user(). */
enum oled_screen {
    OLED_SCREEN_STATUS,
    OLED_SCREEN_STATS,
    OLED_SCREEN_GRAPH,
    OLED_SCREEN_LAYERS,
    OLED_SCREEN_ANIM,                                  // first animation
    OLED_SCREEN_LOGO = OLED_SCREEN_ANIM + SOFLE_ANIM_COUNT,
    OLED_SCREEN_COUNT
};

// Not a screen that can be selected - the animation shown while booting.
#    define SOFLE_SCREEN_BOOT 0xFF

// Holding the OLED key this long starts auto-advancing, so walking through a
// dozen screens is one press and a wait instead of a dozen taps.
#    define SOFLE_OLED_HOLD_MS 400

// WPM readings kept for the graph screen, one per second.
#    define SOFLE_GRAPH_SAMPLES 21

static uint8_t  oled_screen = OLED_SCREEN_STATUS;
static uint32_t oled_boot_time;

// Counted per half: each half only ever sees its own matrix presses (plus the
// other half's, if it happens to be the master), so this is "keys scanned by
// this half", not a keyboard-wide total.
static uint32_t key_count;

static uint8_t wpm_history[SOFLE_GRAPH_SAMPLES];
#endif

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
/*
 * QWERTY
 * ,-----------------------------------------.                    ,-----------------------------------------.
 * |  `   |   1  |   2  |   3  |   4  |   5  |                    |   6  |   7  |   8  |   9  |   0  |  `   |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * | ESC  |   Q  |   W  |   E  |   R  |   T  |                    |   Y  |   U  |   I  |   O  |   P  | Bspc |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * | Tab  |   A  |   S  |   D  |   F  |   G  |-------.    ,-------|   H  |   J  |   K  |   L  |   ;  |  '   |
 * |------+------+------+------+------+------|  MUTE |    |       |------+------+------+------+------+------|
 * |LShift|   Z  |   X  |   C  |   V  |   B  |-------|    |-------|   N  |   M  |   ,  |   .  |   /  |RShift|
 * `-----------------------------------------/       /     \      \-----------------------------------------'
 *            | LGUI | LAlt | LCTR |LOWER | /Enter  /       \Space \  |RAISE | RCTR | RAlt | RGUI |
 *            |      |      |      |      |/       /         \      \ |      |      |      |      |
 *            `----------------------------------'           '------''---------------------------'
 */

[_QWERTY] = LAYOUT(
  KC_GRV,   KC_1,   KC_2,    KC_3,    KC_4,    KC_5,                   KC_6,    KC_7,    KC_8,    KC_9,    KC_0,  KC_GRV,
  KC_ESC,   KC_Q,   KC_W,    KC_E,    KC_R,    KC_T,                     KC_Y,    KC_U,    KC_I,    KC_O,    KC_P,  KC_BSPC,
  KC_TAB,   KC_A,   KC_S,    KC_D,    KC_F,    KC_G,                     KC_H,    KC_J,    KC_K,    KC_L, KC_SCLN,  KC_QUOT,
  KC_LSFT,  KC_Z,   KC_X,    KC_C,    KC_V,    KC_B, KC_MUTE,     KC_MPLY,KC_N,    KC_M, KC_COMM,  KC_DOT, KC_SLSH,  KC_RSFT,
                 KC_LGUI,KC_LALT,KC_LCTL, MO(_LOWER), KC_ENT,      KC_SPC,  MO(_RAISE), KC_RCTL, KC_RALT, KC_RGUI
),
/* LOWER
 * ,-----------------------------------------.                    ,-----------------------------------------.
 * |      |  F1  |  F2  |  F3  |  F4  |  F5  |                    |  F6  |  F7  |  F8  |  F9  | F10  | F11  |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * |  `   |   1  |   2  |   3  |   4  |   5  |                    |   6  |   7  |   8  |   9  |   0  | F12  |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * | Tab  |   !  |   @  |   #  |   $  |   %  |-------.    ,-------|   ^  |   &  |   *  |   (  |   )  |   |  |
 * |------+------+------+------+------+------|  MUTE |    |       |------+------+------+------+------+------|
 * | Shift|  =   |  -   |  +   |   {  |   }  |-------|    |-------|   [  |   ]  |   ;  |   :  |   \  | Shift|
 * `-----------------------------------------/       /     \      \-----------------------------------------'
 *            | LGUI | LAlt | LCTR |LOWER | /Enter  /       \Space \  |RAISE | RCTR | RAlt | RGUI |
 *            |      |      |      |      |/       /         \      \ |      |      |      |      |
 *            `----------------------------------'           '------''---------------------------'
 */
[_LOWER] = LAYOUT(
  _______,   KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,                       KC_F6,   KC_F7,   KC_F8,   KC_F9,  KC_F10,  KC_F11,
  KC_GRV,    KC_1,    KC_2,    KC_3,    KC_4,    KC_5,                       KC_6,    KC_7,    KC_8,    KC_9,    KC_0,  KC_F12,
  _______, KC_EXLM,   KC_AT, KC_HASH,  KC_DLR, KC_PERC,                       KC_CIRC, KC_AMPR, KC_ASTR, KC_LPRN, KC_RPRN, KC_PIPE,
  _______,  KC_EQL, KC_MINS, KC_PLUS, KC_LCBR, KC_RCBR, _______,       _______, KC_LBRC, KC_RBRC, KC_SCLN, KC_COLN, KC_BSLS, _______,
                       _______, _______, _______, _______, _______,       _______, _______, _______, _______, _______
),
/* RAISE
 * ,----------------------------------------.                    ,-----------------------------------------.
 * |      |      |      |      |      |      |                    |      |      |      |      |      |      |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * | Esc  | Ins  | Pscr | Menu |      |      |                    |      | PWrd |  Up  | NWrd | DLine| Bspc |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * | Tab  | LAt  | LCtl |LShift|      | Caps |-------.    ,-------|      | Left | Down | Rigth|  Del | Bspc |
 * |------+------+------+------+------+------|  MUTE  |    |       |------+------+------+------+------+------|
 * |Shift | Undo |  Cut | Copy | Paste|      |-------|    |-------|      | LStr |      | LEnd |      | Shift|
 * `-----------------------------------------/       /     \      \-----------------------------------------'
 *            | LGUI | LAlt | LCTR |LOWER | /Enter  /       \Space \  |RAISE | RCTR | RAlt | RGUI |
 *            |      |      |      |      |/       /         \      \ |      |      |      |      |
 *            `----------------------------------'           '------''---------------------------'
 */
[_RAISE] = LAYOUT(
  _______, _______ , _______ , _______ , _______ , _______,                           _______,  _______  , _______,  _______ ,  _______ ,_______,
  _______,  KC_INS,  KC_PSCR,   KC_APP,  XXXXXXX, XXXXXXX,                        KC_PGUP, KC_PRVWD,   KC_UP, KC_NXTWD,KC_DLINE, KC_BSPC,
  _______, KC_LALT,  KC_LCTL,  KC_LSFT,  XXXXXXX, KC_CAPS,                       KC_PGDN,  KC_LEFT, KC_DOWN, KC_RGHT,  KC_DEL, KC_BSPC,
  _______,KC_UNDO, KC_CUT, KC_COPY, KC_PASTE, XXXXXXX,  _______,       _______,  XXXXXXX, KC_LSTRT, XXXXXXX, KC_LEND,   XXXXXXX, _______,
                         _______, _______, _______, _______, _______,       _______, _______, _______, _______, _______
),
/* ADJUST
 * ,-----------------------------------------.                    ,-----------------------------------------.
 * |      |      |      |      |      |      |                    |      |      |      |      |      |      |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * | QK_BOOT|      |      |OLED |MACWIN|EE_CLR|                    |      |      |      |OLED |      |      |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * |      |      |MACWIN|      |      |      |-------.    ,-------|      | VOLDO| MUTE | VOLUP|      |      |
 * |------+------+------+------+------+------|  MUTE |    |       |------+------+------+------+------+------|
 * |      |      |      |      |      |      |-------|    |-------|      | PREV | PLAY | NEXT |      |      |
 * `-----------------------------------------/       /     \      \-----------------------------------------'
 *            | LGUI | LAlt | LCTR |LOWER | /Enter  /       \Space \  |RAISE | RCTR | RAlt | RGUI |
 *            |      |      |      |      |/       /         \      \ |      |      |      |      |
 *            `----------------------------------'           '------''---------------------------'
 */
  [_ADJUST] = LAYOUT(
  XXXXXXX , XXXXXXX,  XXXXXXX ,  XXXXXXX , XXXXXXX, XXXXXXX,                     XXXXXXX, XXXXXXX, XXXXXXX, XXXXXXX, XXXXXXX, XXXXXXX,
  QK_BOOT  , XXXXXXX, XXXXXXX,OLED_NEXT,CG_TOGG, EE_CLR,                     XXXXXXX, XXXXXXX, XXXXXXX,OLED_NEXT,XXXXXXX, XXXXXXX,
  XXXXXXX , XXXXXXX,CG_TOGG, XXXXXXX,    XXXXXXX,  XXXXXXX,                     XXXXXXX, KC_VOLD, KC_MUTE, KC_VOLU, XXXXXXX, XXXXXXX,
  XXXXXXX , XXXXXXX, XXXXXXX, XXXXXXX,    XXXXXXX,  XXXXXXX, XXXXXXX,     XXXXXXX, XXXXXXX, KC_MPRV, KC_MPLY, KC_MNXT, XXXXXXX, XXXXXXX,
                   _______, _______, _______, _______, _______,     _______, _______, _______, _______, _______
  )
};

#ifdef OLED_ENABLE

/* ------------------------------------------------------------------------
 * OLED layout
 *
 * Both halves run the OLED task independently - oled_task() is called from
 * keyboard_task(), which is not gated on being master - so each half draws
 * its own screen with nothing going over the split link. Each half can show
 * any of the screens below and cycles through them with its own OLED_NEXT key
 * on the ADJUST layer (see housekeeping_task_user()):
 *
 *   status        layer as a 2x banner, mods mode, WPM with a bar, caps lock
 *   anim 0..N-1   one of the SOFLE_ANIM_COUNT loops in oled_anim.h
 *                 (bounce / wave / walk / sleep)
 *   logo          the image in oled_image.h
 *
 * Out of the box the left half starts on status and the right on anim 0.
 *
 * Which half is "left" comes from is_keyboard_left(), i.e. from the
 * handedness in EEPROM, not from whichever half is plugged into USB. The
 * status screen therefore has to keep working when the left half is the
 * slave, which is what the SPLIT_* enables in config.h are for.
 *
 * Both halves use the same rotation, so each has a 64 px wide x 128 px tall
 * canvas: 16 text lines of 8 px.
 *
 *   line  0  +----------------+
 *            |  ------------- |   rule
 *            |      LOWER     |   2x banner (lines 2-3, 16 px)
 *            |  ------------- |   rule
 *            | MODE WIN       |   Mac / Win mode
 *            | MODS C..G      |   live modifiers: C S A G, '.' when not held
 *            | PEAK    88     |   best WPM of the current typing burst
 *            | WPM    42      |
 *            | [--bar-------] |
 *            |                |
 *            | CAPS OFF       |
 *   line 15  +----------------+
 *
 * The animation also plays for SOFLE_BOOT_MS after power-up, on both halves,
 * before settling on the screen each half has selected.
 *
 * If a half comes out upside down once the board is built, swap
 * SOFLE_OLED_ROTATION between 90 and 270 (they differ by 180 degrees).
 * ------------------------------------------------------------------------ */

#    define SOFLE_OLED_ROTATION OLED_ROTATION_90

// A quarter turn swaps the axes, so the canvas is as wide as the panel is
// tall and as tall as the panel is wide.
#    define SOFLE_OLED_WIDTH  OLED_DISPLAY_HEIGHT
#    define SOFLE_OLED_HEIGHT OLED_DISPLAY_WIDTH
#    define SOFLE_OLED_LINES  (SOFLE_OLED_HEIGHT / OLED_FONT_HEIGHT)

#    define SOFLE_ANIM_FPS 8

// Play the animation for this long after power-up, whatever screen is picked.
#    define SOFLE_BOOT_MS 1800

#    include "oled_bigfont.h"
#    include "oled_image.h"

STATIC_ASSERT(SOFLE_OLED_ROTATION == OLED_ROTATION_90 || SOFLE_OLED_ROTATION == OLED_ROTATION_270,
              "SOFLE_OLED_WIDTH/HEIGHT assume the panel sits a quarter turn over");
STATIC_ASSERT(OLED_BIGFONT_H == 2 * OLED_FONT_HEIGHT, "the banner is blitted as two text lines");
STATIC_ASSERT(sizeof(oled_anim[0][0]) == OLED_MATRIX_SIZE, "an animation frame must fill the buffer");

// Where each part of the status screen goes, in text lines. The banner takes
// two, so the rules that bracket it sit on its neighbours' inner edges.
#    define SOFLE_LINE_RULE_TOP    1
#    define SOFLE_LINE_BANNER      2
#    define SOFLE_LINE_RULE_BOTTOM 4
#    define SOFLE_LINE_MODE        6
#    define SOFLE_LINE_MODS        7
#    define SOFLE_LINE_PEAK        8
#    define SOFLE_LINE_WPM         9
#    define SOFLE_LINE_WPM_BAR     10
#    define SOFLE_LINE_CAPS        13

STATIC_ASSERT(SOFLE_LINE_CAPS < SOFLE_OLED_LINES, "the status layout runs off the bottom of the canvas");

/* ------------------------------------------------------------------------
 * Status screen (left half)
 * ------------------------------------------------------------------------ */

// At 12 px per character five characters is all that fits across 64 px, so
// the adjust layer gets shortened rather than silently dropped.
static const char *layer_banner(void) {
    switch (get_highest_layer(layer_state)) {
        case _RAISE:
            return "RAISE";
        case _LOWER:
            return "LOWER";
        case _ADJUST:
            return "ADJ";
        default:
            return "BASE";
    }
}

// The driver's font[] is static, so oled_bigfont.h carries a second, 2x copy
// of the letters the banner can show.
static const char *bigfont_glyph(char c) {
    for (uint8_t i = 0; i < sizeof(oled_bigfont_index) - 1; i++) {
        if (pgm_read_byte(&oled_bigfont_index[i]) == c) {
            return oled_bigfont[i];
        }
    }
    return NULL;
}

// Writes one whole row of the canvas at `line`. Drawing a row at a time is
// what lets the banner be centred exactly: oled_set_cursor() can only address
// 6 px steps, which would leave a 12 px glyph up to 3 px off centre.
static void write_row(uint8_t line, const char *row) {
    oled_set_cursor(0, line);
    oled_write_raw(row, SOFLE_OLED_WIDTH);
}

static void render_banner(uint8_t line, const char *text) {
    static char banner[2][SOFLE_OLED_WIDTH];
    memset(banner, 0, sizeof(banner));

    uint8_t len = strlen(text);
    if (len * OLED_BIGFONT_W > SOFLE_OLED_WIDTH) {
        return; // wider than the canvas, so there is nothing sensible to draw
    }

    uint8_t x = (SOFLE_OLED_WIDTH - len * OLED_BIGFONT_W) / 2;
    for (uint8_t i = 0; i < len; i++, x += OLED_BIGFONT_W) {
        const char *glyph = bigfont_glyph(text[i]);
        if (glyph == NULL) {
            continue;
        }
        for (uint8_t page = 0; page < OLED_BIGFONT_H / 8; page++) {
            memcpy_P(&banner[page][x], glyph + page * OLED_BIGFONT_W, OLED_BIGFONT_W);
        }
    }

    // The glyph is 16 px tall, so it covers this line and the next one.
    write_row(line, banner[0]);
    write_row(line + 1, banner[1]);
}

// A single-pixel rule. `bottom_edge` picks which edge of the row the pixel
// sits on, so the top rule hugs the banner from above and the bottom rule
// hugs it from below.
static void render_rule(uint8_t line, bool bottom_edge) {
    static char rule[SOFLE_OLED_WIDTH];
    memset(rule, bottom_edge ? 0x80 : 0x01, sizeof(rule));
    write_row(line, rule);
}

// Live modifiers, one slot each: the letter when held, '.' when not. Left and
// right of a kind share a slot, since the screen is only 64 px wide.
static void render_mods(void) {
    uint8_t mods = get_mods() | get_oneshot_mods();

    char text[10] = "MODS ....";
    text[5]       = (mods & MOD_MASK_CTRL) ? 'C' : '.';
    text[6]       = (mods & MOD_MASK_SHIFT) ? 'S' : '.';
    text[7]       = (mods & MOD_MASK_ALT) ? 'A' : '.';
    text[8]       = (mods & MOD_MASK_GUI) ? 'G' : '.';
    oled_set_cursor(0, SOFLE_LINE_MODS);
    oled_write_ln(text, false);
}

// The best WPM over the last SOFLE_GRAPH_SAMPLES seconds. Both the status
// screen's PEAK line and the stats screen use this, so they always agree.
static uint8_t wpm_peak(void) {
    uint8_t peak = 0;
    for (uint8_t i = 0; i < SOFLE_GRAPH_SAMPLES; i++) {
        if (wpm_history[i] > peak) {
            peak = wpm_history[i];
        }
    }
    return peak;
}

static void render_wpm(void) {
    uint8_t wpm  = get_current_wpm();
    uint8_t peak = wpm_peak();

    char    text[10] = "WPM    "; // three characters, plus the two digits below
    uint8_t shown    = wpm > 99 ? 99 : wpm;
    text[7]          = '0' + shown / 10;
    text[8]          = '0' + shown % 10;
    oled_set_cursor(0, SOFLE_LINE_WPM);
    oled_write_ln(text, false);

    char    peak_text[10] = "PEAK    ";
    uint8_t shown_peak    = peak > 99 ? 99 : peak;
    peak_text[7]          = '0' + shown_peak / 10;
    peak_text[8]          = '0' + shown_peak % 10;
    oled_set_cursor(0, SOFLE_LINE_PEAK);
    oled_write_ln(peak_text, false);

    const uint8_t first = 5, last = SOFLE_OLED_WIDTH - 5;
    uint8_t       filled = wpm >= 100 ? (uint8_t)(last - first) : (uint8_t)((uint16_t)wpm * (last - first) / 100);

    static char bar[SOFLE_OLED_WIDTH];
    memset(bar, 0, sizeof(bar));
    for (uint8_t x = first; x < last; x++) {
        bar[x] = 0x40; // baseline, so the scale is readable at low WPM
    }
    for (uint8_t x = first; x < first + filled; x++) {
        bar[x] = 0x7e;
    }
    write_row(SOFLE_LINE_WPM_BAR, bar);
}

static void render_status(void) {
    render_rule(SOFLE_LINE_RULE_TOP, true);
    render_banner(SOFLE_LINE_BANNER, layer_banner());
    render_rule(SOFLE_LINE_RULE_BOTTOM, false);

    oled_set_cursor(0, SOFLE_LINE_MODE);
    oled_write_ln_P(keymap_config.swap_lctl_lgui ? PSTR("MODE MAC ") : PSTR("MODE WIN "), false);

    render_mods();
    render_wpm();

    oled_set_cursor(0, SOFLE_LINE_CAPS);
    oled_write_ln_P(host_keyboard_led_state().caps_lock ? PSTR("CAPS ON  ") : PSTR("CAPS OFF "), false);
}

/* ------------------------------------------------------------------------
 * Stats screen
 *
 * The numbers that do not belong on the status screen. KEYS counts what this
 * half scans (the two halves count their own presses); LAYER is the topmost
 * active layer, UP is since power-on.
 * ------------------------------------------------------------------------ */

// Every screen line is exactly nine characters (see render_status()), so the
// label is placed and the rest is padded - never ten characters.
static void line_start(char *text, const char *label) {
    memset(text, ' ', 9);
    text[9] = '\0';
    memcpy(text, label, strlen(label));
}

static void render_stats(void) {
    uint32_t keys  = key_count > 99999 ? 99999 : key_count;
    uint32_t secs  = timer_read32() / 1000;
    uint32_t mins  = secs / 60;
    uint32_t hours = mins / 60;
    uint8_t  wpm   = get_current_wpm();
    uint8_t  peak  = wpm_peak();
    if (wpm > 99) {
        wpm = 99;
    }
    if (peak > 99) {
        peak = 99;
    }

    char text[10];

    render_rule(SOFLE_LINE_RULE_TOP, true);
    render_banner(SOFLE_LINE_BANNER, "STATS");
    render_rule(SOFLE_LINE_RULE_BOTTOM, false);

    line_start(text, "KEY"); // "KEY 12345"
    for (uint8_t i = 0; i < 5; i++) {
        text[8 - i] = '0' + keys % 10;
        keys /= 10;
    }
    oled_set_cursor(0, SOFLE_LINE_MODE);
    oled_write_ln(text, false);

    line_start(text, "WPM"); // "WPM    42"
    text[7] = '0' + wpm / 10;
    text[8] = '0' + wpm % 10;
    oled_set_cursor(0, SOFLE_LINE_MODS);
    oled_write_ln(text, false);

    line_start(text, "PEAK"); // "PEAK   88"
    text[7] = '0' + peak / 10;
    text[8] = '0' + peak % 10;
    oled_set_cursor(0, SOFLE_LINE_PEAK);
    oled_write_ln(text, false);

    line_start(text, "LAYER"); // "LAYER   2"
    text[8] = '0' + get_highest_layer(layer_state | default_layer_state);
    oled_set_cursor(0, SOFLE_LINE_WPM);
    oled_write_ln(text, false);

    line_start(text, "UP"); // "UP  03:21"
    text[4] = '0' + (hours / 10) % 10;
    text[5] = '0' + hours % 10;
    text[6] = ':';
    text[7] = '0' + (mins % 60) / 10;
    text[8] = '0' + (mins % 60) % 10;
    oled_set_cursor(0, SOFLE_LINE_WPM_BAR);
    oled_write_ln(text, false);

    oled_set_cursor(0, SOFLE_LINE_CAPS);
    oled_write_ln_P(host_keyboard_led_state().caps_lock ? PSTR("CAPS ON  ") : PSTR("CAPS OFF "), false);
}

/*
 * The graph and the layers screen share the lines below the banner with the
 * status screen, so they use the same SOFLE_LINE_* constants.
 */

/* ------------------------------------------------------------------------
 * Graph screen
 *
 * The current WPM in 2x digits, with the last SOFLE_GRAPH_SAMPLES seconds as a
 * scrolling bar chart along the bottom. WPM is mirrored over the split link,
 * so both halves draw the same chart.
 * ------------------------------------------------------------------------ */

// Called on every OLED frame whatever the screen, so PEAK and the graph keep
// up even if the graph is not the screen being shown.
static void wpm_history_sample(void) {
    static uint32_t next_sample;

    if (timer_elapsed32(next_sample) < 1000) {
        return;
    }
    next_sample = timer_read32();

    memmove(&wpm_history[0], &wpm_history[1], SOFLE_GRAPH_SAMPLES - 1);
    wpm_history[SOFLE_GRAPH_SAMPLES - 1] = get_current_wpm();
}

static void render_graph(void) {
    uint8_t wpm = get_current_wpm();
    wpm         = wpm > 99 ? 99 : wpm;

    char big[3] = {'0' + wpm / 10, '0' + wpm % 10, '\0'};
    render_rule(SOFLE_LINE_RULE_TOP, true);
    render_banner(SOFLE_LINE_BANNER, big);

    oled_set_cursor(0, SOFLE_LINE_MODE);
    oled_write_ln("WPM      ", false);

    // 21 bars, 3 px apart: 2 px of bar and 1 px of gap
    const uint8_t chart_line = SOFLE_LINE_WPM;   // bars start 8 px text lines down
    const uint8_t chart_h    = SOFLE_OLED_HEIGHT - chart_line * OLED_FONT_HEIGHT;

    for (uint8_t page = 0; page < chart_h / 8; page++) {
        char row[SOFLE_OLED_WIDTH];
        memset(row, 0, sizeof(row));

        for (uint8_t i = 0; i < SOFLE_GRAPH_SAMPLES; i++) {
            uint8_t height = (uint16_t)wpm_history[i] * chart_h / 100;
            for (uint8_t w = 0; w < 2; w++) {
                uint8_t x = 1 + i * 3 + w;
                if (x >= SOFLE_OLED_WIDTH) {
                    continue;
                }
                for (uint8_t bit = 0; bit < 8; bit++) {
                    uint8_t y = chart_line * OLED_FONT_HEIGHT + page * 8 + bit;
                    if (SOFLE_OLED_HEIGHT - 1 - y < height) {
                        row[x] |= 1 << bit;
                    }
                }
            }
        }
        write_row(chart_line + page, row);
    }
}

/* ------------------------------------------------------------------------
 * Layers screen
 *
 * Which of the four layers are active. LOWER and RAISE are only on while held,
 * and both together bring up ADJUST (update_tri_layer_state), so this is also
 * a way to see the tri-layer do its thing.
 * ------------------------------------------------------------------------ */

static void render_layers(void) {
    static const char *const names[] = {"BASE", "LOWER", "RAISE", "ADJ"};
    layer_state_t           active  = layer_state | default_layer_state;
    char                    text[11];

    render_rule(SOFLE_LINE_RULE_TOP, true);
    render_banner(SOFLE_LINE_BANNER, "LAYER");
    render_rule(SOFLE_LINE_RULE_BOTTOM, false);

    for (uint8_t i = 0; i < 4; i++) {
        bool        on    = active & ((layer_state_t)1 << i);
        const char *state = on ? "ON" : "OFF";
        uint8_t     len   = strlen(names[i]);
        uint8_t     pad   = 9 - len - strlen(state);

        // nine characters: name, padding, then "ON" or "OFF"
        memset(text, ' ', sizeof(text));
        memcpy(text, names[i], len);
        memcpy(text + len + pad, state, strlen(state));
        text[9] = '\0';

        oled_set_cursor(0, SOFLE_LINE_MODE + i);
        oled_write_ln(text, false);
    }

    oled_set_cursor(0, SOFLE_LINE_CAPS);
    oled_write_ln_P(keymap_config.swap_lctl_lgui ? PSTR("MODE MAC ") : PSTR("MODE WIN "), false);
}

/* ------------------------------------------------------------------------
 * Logo screen
 * ------------------------------------------------------------------------ */

// oled_image.h is 64 x 96 px of page format, so it covers lines 0-11 and the
// bottom of the canvas stays blank.
static void render_logo(void) {
    oled_set_cursor(0, 0);
    oled_write_raw_P(oled_image, sizeof(oled_image));
}

/* ------------------------------------------------------------------------
 * Animation screen
 * ------------------------------------------------------------------------ */

// One of the SOFLE_ANIM_COUNT loops in oled_anim.h. The frame counter is
// shared, so switching animation picks up wherever the old one was, which is
// fine - every loop is the same length.
static void render_animation(uint8_t which) {
    static uint32_t next_frame;
    static uint8_t  frame;

    if (timer_elapsed32(next_frame) >= 1000 / SOFLE_ANIM_FPS) {
        next_frame = timer_read32();
        frame      = (frame + 1) % SOFLE_ANIM_FRAMES;
    }

    oled_set_cursor(0, 0);
    oled_write_raw_P(oled_anim[which][frame], sizeof(oled_anim[0][0]));
}

oled_rotation_t oled_init_user(oled_rotation_t rotation) {
    return SOFLE_OLED_ROTATION;
}

/* ------------------------------------------------------------------------
 * Every string on the status screen is exactly nine characters long, and is
 * only ever written with oled_write_ln(). That is not cosmetic. The driver's
 * font is fixed width with 10 characters to a line, and oled_advance_page()
 * pads out the remainder one character at a time: a nine character line
 * leaves room for exactly one pad space, which lands the cursor on the next
 * line. Ten characters would leave the cursor already wrapped and make that
 * pad wipe the line below; eight would leave room for two and spill one of
 * them onto it.
 * ------------------------------------------------------------------------ */

bool oled_task_user(void) {
    wpm_history_sample();

    // The animation plays for a moment after power-up on both halves, then
    // each half settles on whatever screen it has selected.
    uint8_t want = timer_elapsed32(oled_boot_time) < SOFLE_BOOT_MS ? SOFLE_SCREEN_BOOT : oled_screen;

    // Switching screens leaves the previous one's pixels behind - the status
    // screen only paints some of the rows and the logo only the top 96 - so
    // blank the buffer whenever the screen changes.
    static uint8_t drawn = 0xFF;
    if (drawn != want) {
        oled_clear();
        drawn = want;
    }

    if (want == SOFLE_SCREEN_BOOT) {
        render_animation(0); // the hop is the "hello" one
    } else if (want >= OLED_SCREEN_ANIM && want < OLED_SCREEN_LOGO) {
        render_animation(want - OLED_SCREEN_ANIM);
    } else if (want == OLED_SCREEN_LOGO) {
        render_logo();
    } else if (want == OLED_SCREEN_STATS) {
        render_stats();
    } else if (want == OLED_SCREEN_GRAPH) {
        render_graph();
    } else if (want == OLED_SCREEN_LAYERS) {
        render_layers();
    } else {
        render_status();
    }
    return false;
}

// Out of the box: status on the left, the first animation on the right.
void keyboard_post_init_user(void) {
    oled_screen    = is_keyboard_left() ? OLED_SCREEN_STATUS : OLED_SCREEN_ANIM;
    oled_boot_time = timer_read32();
}

/* ------------------------------------------------------------------------
 * OLED screen switch
 *
 * Both halves run their own OLED, and process_record_user() only ever runs on
 * the master, so a keycode cannot simply set a shared variable: the slave
 * would never hear about it. Instead each half watches *its own* matrix rows
 * (matrix_get_row() holds the local half's rows at their global indices on
 * both halves) and flips its own screen when the key that the keymap puts
 * there is pressed. So the OLED_NEXT key on the left half switches the left
 * screen, the one on the right half switches the right one, and neither half
 * needs to know anything about the other.
 *
 * The lookup reads the compiled keymap rather than VIA's EEPROM copy, so both
 * halves agree even though only the master's EEPROM is ever remapped. Layer
 * transparency is walked the same way the keycode lookup does it, top layer
 * first.
 * ------------------------------------------------------------------------ */

static bool oled_switch_key(uint8_t row, uint8_t col) {
    layer_state_t layers = layer_state | default_layer_state;

    for (int8_t layer = MAX_LAYER - 1; layer >= 0; layer--) {
        if (!(layers & ((layer_state_t)1 << layer))) {
            continue;
        }
        uint16_t keycode = keycode_at_keymap_location_raw(layer, row, col);
        if (keycode != KC_TRANSPARENT) {
            return keycode == OLED_NEXT; // topmost concrete keycode wins
        }
    }
    return false;
}

void housekeeping_task_user(void) {
    static matrix_row_t last[MATRIX_ROWS_PER_HAND];
    static uint8_t      held_row = 0xFF, held_col;
    static uint32_t     last_advance;

    for (uint8_t i = 0; i < MATRIX_ROWS_PER_HAND; i++) {
        uint8_t      row = is_keyboard_left() ? i : i + MATRIX_ROWS_PER_HAND;
        matrix_row_t now = matrix_get_row(row);
        matrix_row_t hit = now & ~last[i];
        last[i]          = now;

        while (hit) {
            uint8_t col = __builtin_ctz(hit);
            hit &= hit - 1;

            if (oled_switch_key(row, col)) {
                oled_screen  = (oled_screen + 1) % OLED_SCREEN_COUNT;
                held_row     = row;
                held_col     = col;
                last_advance = timer_read32();
            } else {
                key_count++; // the display key is not typing
            }
        }
    }

    // Keep advancing while the key is held, so walking through a dozen screens
    // is one press and a wait rather than a dozen taps.
    if (held_row != 0xFF) {
        if (!matrix_is_on(held_row, held_col)) {
            held_row = 0xFF;
        } else if (timer_elapsed32(last_advance) >= SOFLE_OLED_HOLD_MS) {
            oled_screen  = (oled_screen + 1) % OLED_SCREEN_COUNT;
            last_advance = timer_read32();
        }
    }
}

#endif

layer_state_t layer_state_set_user(layer_state_t state) {
    return update_tri_layer_state(state, _LOWER, _RAISE, _ADJUST);
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case OLED_NEXT:
            // Not handled here: only the master sees keycodes, and both halves
            // need to switch, so housekeeping_task_user() picks this up on the
            // half the key actually sits on. Swallow it so nothing else sees it.
            return false;
        case KC_PRVWD:
            if (record->event.pressed) {
                if (keymap_config.swap_lctl_lgui) {
                    register_mods(mod_config(MOD_LALT));
                    register_code(KC_LEFT);
                } else {
                    register_mods(mod_config(MOD_LCTL));
                    register_code(KC_LEFT);
                }
            } else {
                if (keymap_config.swap_lctl_lgui) {
                    unregister_mods(mod_config(MOD_LALT));
                    unregister_code(KC_LEFT);
                } else {
                    unregister_mods(mod_config(MOD_LCTL));
                    unregister_code(KC_LEFT);
                }
            }
            break;
        case KC_NXTWD:
             if (record->event.pressed) {
                if (keymap_config.swap_lctl_lgui) {
                    register_mods(mod_config(MOD_LALT));
                    register_code(KC_RIGHT);
                } else {
                    register_mods(mod_config(MOD_LCTL));
                    register_code(KC_RIGHT);
                }
            } else {
                if (keymap_config.swap_lctl_lgui) {
                    unregister_mods(mod_config(MOD_LALT));
                    unregister_code(KC_RIGHT);
                } else {
                    unregister_mods(mod_config(MOD_LCTL));
                    unregister_code(KC_RIGHT);
                }
            }
            break;
        case KC_LSTRT:
            if (record->event.pressed) {
                if (keymap_config.swap_lctl_lgui) {
                     //CMD-arrow on Mac, but we have CTL and GUI swapped
                    register_mods(mod_config(MOD_LCTL));
                    register_code(KC_LEFT);
                } else {
                    register_code(KC_HOME);
                }
            } else {
                if (keymap_config.swap_lctl_lgui) {
                    unregister_mods(mod_config(MOD_LCTL));
                    unregister_code(KC_LEFT);
                } else {
                    unregister_code(KC_HOME);
                }
            }
            break;
        case KC_LEND:
            if (record->event.pressed) {
                if (keymap_config.swap_lctl_lgui) {
                    //CMD-arrow on Mac, but we have CTL and GUI swapped
                    register_mods(mod_config(MOD_LCTL));
                    register_code(KC_RIGHT);
                } else {
                    register_code(KC_END);
                }
            } else {
                if (keymap_config.swap_lctl_lgui) {
                    unregister_mods(mod_config(MOD_LCTL));
                    unregister_code(KC_RIGHT);
                } else {
                    unregister_code(KC_END);
                }
            }
            break;
        case KC_DLINE:
            if (record->event.pressed) {
                register_mods(mod_config(MOD_LCTL));
                register_code(KC_BSPC);
            } else {
                unregister_mods(mod_config(MOD_LCTL));
                unregister_code(KC_BSPC);
            }
            break;
        case KC_COPY:
            if (record->event.pressed) {
                register_mods(mod_config(MOD_LCTL));
                register_code(KC_C);
            } else {
                unregister_mods(mod_config(MOD_LCTL));
                unregister_code(KC_C);
            }
            return false;
        case KC_PASTE:
            if (record->event.pressed) {
                register_mods(mod_config(MOD_LCTL));
                register_code(KC_V);
            } else {
                unregister_mods(mod_config(MOD_LCTL));
                unregister_code(KC_V);
            }
            return false;
        case KC_CUT:
            if (record->event.pressed) {
                register_mods(mod_config(MOD_LCTL));
                register_code(KC_X);
            } else {
                unregister_mods(mod_config(MOD_LCTL));
                unregister_code(KC_X);
            }
            return false;
            break;
        case KC_UNDO:
            if (record->event.pressed) {
                register_mods(mod_config(MOD_LCTL));
                register_code(KC_Z);
            } else {
                unregister_mods(mod_config(MOD_LCTL));
                unregister_code(KC_Z);
            }
            return false;
    }
    return true;
}


/* ------------------------------------------------------------------------
 * Encoders
 *
 * One entry per encoder, in hardware order: index 0 is the left half's knob,
 * index 1 the right half's. The index is decided by the physical side, not by
 * which half is master - the driver adds NUM_ENCODERS_LEFT for the right half
 * (drivers/encoder/encoder_quadrature.c) - so both slots have to be filled.
 *
 * Left  knob: volume, and its push switch (matrix [4, 5]) is KC_MUTE.
 * Right knob: previous/next track, and its push switch (matrix [9, 5]) is
 * KC_MPLY. Only the base entries are written; the layers above are KC_TRNS so
 * the knob keeps working everywhere and falls through to them.
 *
 * If a knob turns the wrong way, swap the two keycodes in its pair.
 * ------------------------------------------------------------------------ */

#ifdef ENCODER_MAP_ENABLE
    const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][NUM_DIRECTIONS] = {
        //        left knob                        right knob
       [0] = { ENCODER_CCW_CW(KC_VOLD, KC_VOLU),   ENCODER_CCW_CW(KC_MPRV, KC_MNXT) },
       [1] = { ENCODER_CCW_CW(_______, _______),  ENCODER_CCW_CW(_______, _______) },
       [2] = { ENCODER_CCW_CW(_______, _______),  ENCODER_CCW_CW(_______, _______) },
       [3] = { ENCODER_CCW_CW(_______, _______),  ENCODER_CCW_CW(_______, _______) },
      };
#endif

