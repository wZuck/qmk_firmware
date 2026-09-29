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
/* What each half draws. The choice is per half and lives in RAM only, so a
 * power cycle goes back to the defaults set in keyboard_post_init_user(). */
enum oled_screen {
    OLED_SCREEN_STATUS,
    OLED_SCREEN_ANIM,
    OLED_SCREEN_LOGO,
    OLED_SCREEN_COUNT
};

// Not a screen that can be selected - the animation shown while booting.
#    define SOFLE_SCREEN_BOOT 0xFF

static uint8_t  oled_screen = OLED_SCREEN_STATUS;
static uint32_t oled_boot_time;
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
 * any of three screens and cycles through them with its own OLED_NEXT key on
 * the ADJUST layer (see housekeeping_task_user()):
 *
 *   status  layer as a 2x banner, mods mode, WPM with a bar, caps lock
 *   anim    the animation in oled_anim.h
 *   logo    the image in oled_image.h
 *
 * Out of the box the left half starts on status and the right on anim.
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

#    include "oled_anim.h"
#    include "oled_bigfont.h"
#    include "oled_image.h"

STATIC_ASSERT(SOFLE_OLED_ROTATION == OLED_ROTATION_90 || SOFLE_OLED_ROTATION == OLED_ROTATION_270,
              "SOFLE_OLED_WIDTH/HEIGHT assume the panel sits a quarter turn over");
STATIC_ASSERT(OLED_BIGFONT_H == 2 * OLED_FONT_HEIGHT, "the banner is blitted as two text lines");
STATIC_ASSERT(sizeof(oled_anim[0]) == OLED_MATRIX_SIZE, "an animation frame must fill the buffer");

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

static void render_wpm(void) {
    uint8_t wpm = get_current_wpm();

    // "Peak" is per typing burst rather than per power cycle: it tracks the
    // best WPM while typing, and is dropped once the typing stops for a bit.
    static uint8_t  peak;
    static uint32_t last_active;
    if (wpm > 0) {
        last_active = timer_read32();
        if (wpm > peak) {
            peak = wpm;
        }
    } else if (peak > 0 && timer_elapsed32(last_active) > 5000) {
        peak = 0;
    }

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

static void render_animation(void) {
    static uint32_t next_frame;
    static uint8_t  frame;

    if (timer_elapsed32(next_frame) >= 1000 / SOFLE_ANIM_FPS) {
        next_frame = timer_read32();
        frame      = (frame + 1) % SOFLE_ANIM_FRAMES;
    }

    oled_set_cursor(0, 0);
    oled_write_raw_P(oled_anim[frame], sizeof(oled_anim[0]));
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

    switch (want) {
        case SOFLE_SCREEN_BOOT:
        case OLED_SCREEN_ANIM:
            render_animation();
            break;
        case OLED_SCREEN_LOGO:
            render_logo();
            break;
        default:
            render_status();
            break;
    }
    return false;
}

// Out of the box: status on the left, mascot on the right.
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

    for (uint8_t i = 0; i < MATRIX_ROWS_PER_HAND; i++) {
        uint8_t      row = is_keyboard_left() ? i : i + MATRIX_ROWS_PER_HAND;
        matrix_row_t now = matrix_get_row(row);
        matrix_row_t hit = now & ~last[i];
        last[i]          = now;

        while (hit) {
            uint8_t col = __builtin_ctz(hit);
            hit &= hit - 1;
            if (oled_switch_key(row, col)) {
                oled_screen = (oled_screen + 1) % OLED_SCREEN_COUNT;
            }
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

