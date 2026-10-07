// Copyright 2023 Ryan Neff (@JellyTitan)
// SPDX-License-Identifier: GPL-2.0-or-later

#include QMK_KEYBOARD_H
// Not pulled in by quantum.h, needed for keycode_at_keymap_location_raw()
#include "keymap_introspection.h"
#ifdef SPLIT_KEYBOARD
// Also not pulled in by quantum.h: transaction_register_rpc() and
// transaction_rpc_exec(), the split transport's user transaction API the OLED
// screensaver syncs its "did you see a key?" token over. See
// SOFLE_SCREENSAVER_SYNC and SPLIT_TRANSACTION_IDS_USER in config.h.
#    include "transactions.h"
#endif

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
    KC_DLINE,
#ifdef RGB_MATRIX_ENABLE
    /* 灯效直达：按一下就把灯效换成指定的一种，不用拿 RM_NEXT 一圈圈翻。
     * 第一个是出厂默认的「纯白常亮」（keyboard.json 里 default.animation =
     * solid_color、sat = 0），其余 8 种就是 build_soflepico/ 里做了演示动画的那 8 种。 */
    FX_WHITE,
    FX_CYCLE_OUT_IN,
    FX_HUE_WAVE,
    FX_RAINBOW_BEACON,
    FX_PIXEL_FLOW,
    FX_JELLYBEAN,
    FX_DIGITAL_RAIN,
    FX_REACTIVE_NEXUS,
    FX_TYPING_HEATMAP,
#endif
};

/* 没有编进 RGB 的构建（比如排查用的 probe keymap 抄了这份键位）：
 * 把灯效键退化成空键，键位表本身不用改。 */
#ifndef RGB_MATRIX_ENABLE
#    define RM_TOGG  XXXXXXX
#    define RM_NEXT  XXXXXXX
#    define RM_PREV  XXXXXXX
#    define RM_VALU  XXXXXXX
#    define RM_VALD  XXXXXXX
#    define RM_HUEU  XXXXXXX
#    define RM_HUED  XXXXXXX
#    define RM_SATU  XXXXXXX
#    define RM_SATD  XXXXXXX
#    define RM_SPDU  XXXXXXX
#    define RM_SPDD  XXXXXXX
#    define FX_WHITE          XXXXXXX
#    define FX_CYCLE_OUT_IN    XXXXXXX
#    define FX_HUE_WAVE        XXXXXXX
#    define FX_RAINBOW_BEACON  XXXXXXX
#    define FX_PIXEL_FLOW      XXXXXXX
#    define FX_JELLYBEAN       XXXXXXX
#    define FX_DIGITAL_RAIN    XXXXXXX
#    define FX_REACTIVE_NEXUS  XXXXXXX
#    define FX_TYPING_HEATMAP  XXXXXXX
#endif

#ifdef OLED_ENABLE
// The animation library: SOFLE_ANIM_COUNT loops of SOFLE_ANIM_FRAMES frames.
#    include "oled_anim.h"
// The same loops with every pixel flipped, for the inverted screens.
#    include "oled_anim_inv.h"
// The snowboarding pair, in both polarities (oled_snow.h).
#    include "oled_snow.h"

// The snow set is two drawings and has no loops to pick between, so it gets one
// screen per polarity that alternates them.
#    define SOFLE_SNOW_COUNT 1

/* What each half draws. Every animation counts as its own screen, so the OLED
 * key walks status -> stats -> graph -> layers -> 4 mascot loops -> 4 inverted
 * mascot loops -> snow -> inverted snow -> status, and holding it down
 * auto-advances. The choice is per half and lives in RAM only, so a power cycle
 * goes back to the defaults set in keyboard_post_init_user(). */
enum oled_screen {
    OLED_SCREEN_STATUS,
    OLED_SCREEN_STATS,
    OLED_SCREEN_GRAPH,
    OLED_SCREEN_LAYERS,
    OLED_SCREEN_ANIM,                                           // mascot, lit on dark
    OLED_SCREEN_ANIM_INV = OLED_SCREEN_ANIM + SOFLE_ANIM_COUNT,  // mascot, dark on lit
    OLED_SCREEN_SNOW     = OLED_SCREEN_ANIM_INV + SOFLE_ANIM_INV_COUNT,
    OLED_SCREEN_SNOW_INV = OLED_SCREEN_SNOW + SOFLE_SNOW_COUNT,
    OLED_SCREEN_COUNT
};

// Which animation loop is the sleeping mascot (the zzz one, see oled_anim.h).
#    define SOFLE_ANIM_SLEEP 3

// Not a screen that can be selected - the animation shown while booting.
#    define SOFLE_SCREEN_BOOT 0xFF

// Nor this one: the "screensaver" the half drops into when nothing has been
// typed on it for SOFLE_SLEEP_MS, and the screen it comes back to as soon as
// a key goes down.
#    define SOFLE_SCREEN_SLEEP 0xFE

/* How long the *keyboard* has to go without a key press before both halves
 * fall asleep together.
 *
 * Each half times its own keys (see housekeeping_task_user()), which alone
 * would let one half sleep while you type on the other, so the master also
 * asks the slave whether it saw a key - that is what SOFLE_SCREENSAVER_SYNC
 * is, and why this is a shared "nobody typed anywhere" clock rather than a
 * per-half one. */
#    define SOFLE_SLEEP_MS 60000

/* How often the master asks the slave "did you see a key?". This bounds how
 * stale the other half's answer can be, so it is also the margin the two
 * halves can differ by when falling asleep - they can never wake apart, since
 * each half always wakes on its own local key press. 250 ms keeps that
 * margin invisible without putting a transaction on the wire every scan. */
#    define SOFLE_SLEEP_SYNC_MS 250

/* The transaction that carries the activity token between the halves (see
 * SPLIT_TRANSACTION_IDS_USER in config.h). It is an enum constant, not a
 * macro: the serial_transaction_id enum in transaction_id_define.h already
 * gives it a value, and QMK assigns those in order precisely so a keymap only
 * has to name it. */
STATIC_ASSERT(SOFLE_SCREENSAVER_SYNC > GET_RPC_RESP_DATA,
              "SOFLE_SCREENSAVER_SYNC must be a user-level transaction id, not a core one");

// Holding the OLED key this long starts auto-advancing, so walking through a
// dozen screens is one press and a wait instead of a dozen taps.
#    define SOFLE_OLED_HOLD_MS 400

// WPM readings kept for the graph screen, one per second.
#    define SOFLE_GRAPH_SAMPLES 21

static uint8_t  oled_screen = OLED_SCREEN_STATUS;
static uint32_t oled_boot_time;

/* Screensaver state, one set per half:
 *   oled_sleeping  - this half is showing the sleeping mascot right now
 *   last_activity  - when a key last went down on *either* half (each half
 *                    starts it on its own presses; the split exchange below
 *                    feeds in the other one's)
 *   saw_activity   - a key of this half went down since the last exchange; the
 *                    token that travels over SOFLE_SCREENSAVER_SYNC
 *   peer_activity  - the other half's token, as last reported
 * The animation clock lives up here rather than inside render_animation() so
 * the mascot keeps breathing at SOFLE_ANIM_FPS whatever screen is up, and so
 * waking from the screensaver resumes the loop where it left off. */
static bool     oled_sleeping;
static uint32_t last_activity;
static bool     saw_activity;  // a key of this half went down since the last exchange
static bool     peer_activity; // the other half reported a key at the last exchange
static uint32_t oled_frame_time;
static uint8_t  oled_frame;

// What the screensaver asks the other half, and what it answers with: the two
// fields are the same on both sides, only the direction differs.
typedef struct __attribute__((packed)) {
    uint8_t saw_activity; // 1 if a key went down on this half since the last exchange
} sofle_activity_sync_t;

// Defined with the rest of the screensaver code further down; registered here
// because keyboard_post_init_user() is where the transport wants it.
static void screensaver_sync_slave_handler(uint8_t in_buflen, const void *in_data, uint8_t out_buflen, void *out_data);

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
/* ADJUST —— 系统键 + 灯光控制
 *
 * 灯光调整分成左右两组，各自成对（- 在前、+ 在后）：
 *   左手 row0：开关 / 切灯效 / 亮度
 *   右手 row0：色相 / 饱和 / 速度
 * 另外两个旋钮在这一层临时改成调灯：左旋钮=亮度、右旋钮=速度
 * （旋钮按压键也借来用：左=灯光开关、右=下一个灯效）。
 * 原来放在这一层的媒体键（上一首/播放/下一首）挪到右边 row2 col5-6 与
 * row3 col5，位置变了但都还在。
 *
 * 灯效直达键在 row3 最左边 4~5 列（左手 5 个、右手 4 个）：
 *   FX_WHITE          纯白常亮（出厂默认）
 *   FX_CYCLE_OUT_IN   单色光波从中心扩散
 *   FX_HUE_WAVE       彩虹波浪横扫
 *   FX_RAINBOW_BEACON 彩虹双信标旋转
 *   FX_PIXEL_FLOW     像素流
 *   FX_JELLYBEAN      随机彩色雨滴
 *   FX_DIGITAL_RAIN   数字雨
 *   FX_REACTIVE_NEXUS 按键涟漪（从按键向四周扩散）
 *   FX_TYPING_HEATMAP 打字热图（按过的地方亮起来再慢慢冷掉）
 *
 * 雪人那套图不占按键：它是 OLED 循环里的画面（正色一屏、反色一屏，排在四组动画之后），
 * 用原来那个 OLED 键就能翻到，见 oled_snow.h。
 *
 * ,-----------------------------------------.                    ,-----------------------------------------.
 * |RM_TOGG|RM_NEXT|RM_PREV|RM_VALU|RM_VALD|      |               |RM_HUEU|RM_HUED|RM_SATU|RM_SATD|RM_SPDU|RM_SPDD|
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * | QK_BOOT|      |      |OLED |MACWIN|EE_CLR|                    |      |      |      |OLED |      |      |
 * |------+------+------+------+------+------|                    |------+------+------+------+------+------|
 * |      |      |MACWIN|      |      |      |-------.    ,-------|      | VOLDO| MUTE | VOLUP| PREV | NEXT |
 * |------+------+------+------+------+------| RM_TOG |    |RM_NEXT|------+------+------+------+------+------|
 * |纯白  |波扩散|彩虹波|信标  |像素流|      |-------|    |-------|彩点  |数字雨|涟漪  |热图  | PLAY |      |
 * `-----------------------------------------/       /     \      \-----------------------------------------'
 *            | LGUI | LAlt | LCTR |LOWER | /Enter  /       \Space \  |RAISE | RCTR | RAlt | RGUI |
 *            |      |      |      |      |/       /         \      \ |      |      |      |      |
 *            `----------------------------------'           '------''---------------------------'
 */
  [_ADJUST] = LAYOUT(
  RM_TOGG  , RM_NEXT,  RM_PREV,  RM_VALU,  RM_VALD, XXXXXXX,                     RM_HUEU, RM_HUED, RM_SATU, RM_SATD, RM_SPDU, RM_SPDD,
  QK_BOOT  , XXXXXXX, XXXXXXX,OLED_NEXT,CG_TOGG, EE_CLR,                     XXXXXXX, XXXXXXX, XXXXXXX,OLED_NEXT,XXXXXXX, XXXXXXX,
  XXXXXXX  , XXXXXXX,CG_TOGG, XXXXXXX,    XXXXXXX,  XXXXXXX,                     XXXXXXX, KC_VOLD, KC_MUTE, KC_VOLU, KC_MPRV, KC_MNXT,
  FX_WHITE, FX_CYCLE_OUT_IN, FX_HUE_WAVE, FX_RAINBOW_BEACON, FX_PIXEL_FLOW, XXXXXXX, RM_TOGG, RM_NEXT, FX_JELLYBEAN, FX_DIGITAL_RAIN, FX_REACTIVE_NEXUS, FX_TYPING_HEATMAP, KC_MPLY, XXXXXXX,
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
 *   stats         keys / WPM / layer / uptime
 *   graph         current WPM in 2x with a 21 second bar chart
 *   layers        which of the four layers are on
 *   anim 0..N-1   one of the SOFLE_ANIM_COUNT loops in oled_anim.h
 *                 (bounce / wave / walk / sleep)
 *   anim inv      the same loops out of oled_anim_inv.h, every pixel flipped
 *   snow          the snowboarding pair in oled_snow.h, and its inverted twin
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
 * On top of that sits the screensaver: SOFLE_SLEEP_MS (a minute) with no key
 * pressed on *either* half and both halves drop into the sleeping mascot - the
 * zzz loop from oled_anim.h - and the first key anywhere brings both back to
 * whatever screen each half was on. Sleeping is agreed between the two halves
 * over the split; waking is each half's own business. See the screensaver note
 * further down.
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

STATIC_ASSERT(SOFLE_OLED_ROTATION == OLED_ROTATION_90 || SOFLE_OLED_ROTATION == OLED_ROTATION_270,
              "SOFLE_OLED_WIDTH/HEIGHT assume the panel sits a quarter turn over");
STATIC_ASSERT(OLED_BIGFONT_H == 2 * OLED_FONT_HEIGHT, "the banner is blitted as two text lines");
STATIC_ASSERT(sizeof(oled_anim[0][0]) == OLED_MATRIX_SIZE, "an animation frame must fill the buffer");
STATIC_ASSERT(sizeof(oled_anim_inv[0][0]) == OLED_MATRIX_SIZE, "an inverted frame must fill the buffer too");
STATIC_ASSERT(sizeof(oled_snow[0]) == OLED_MATRIX_SIZE, "a snow frame must fill the buffer too");
STATIC_ASSERT(sizeof(oled_snow_inv[0]) == OLED_MATRIX_SIZE, "an inverted snow frame must fill the buffer too");
STATIC_ASSERT(SOFLE_ANIM_INV_COUNT == SOFLE_ANIM_COUNT, "the inverted set mirrors the normal one loop for loop");
STATIC_ASSERT(SOFLE_SNOW_FRAMES >= 2, "the snow set is a two-drawing loop; one frame would be a still");

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
 * Animation screen
 * ------------------------------------------------------------------------ */

// The shared frame clock behind every animation: called once per OLED frame
// from oled_task_user(), whatever is on screen. It always counts the mascot's
// frames, even while the snow art is selected; the two art sets wrap it to
// their own length, so the snow pair alternates at SOFLE_ANIM_FPS / 2 rather
// than four times a second.
static void anim_advance_frame(void) {
    if (timer_elapsed32(oled_frame_time) >= 1000 / SOFLE_ANIM_FPS) {
        oled_frame_time = timer_read32();
        oled_frame      = (oled_frame + 1) % SOFLE_ANIM_FRAMES;
    }
}

// One of the SOFLE_ANIM_COUNT animation loops in oled_anim.h.
static void render_animation(uint8_t which) {
    oled_set_cursor(0, 0);
    oled_write_raw_P(oled_anim[which][oled_frame], sizeof(oled_anim[0][0]));
}

// The same loop out of oled_anim_inv.h, i.e. the day version of it.
static void render_animation_inv(uint8_t which) {
    oled_set_cursor(0, 0);
    oled_write_raw_P(oled_anim_inv[which][oled_frame], sizeof(oled_anim_inv[0][0]));
}

// The snow screen: the two drawings from oled_snow.h, alternating. It wraps the
// shared frame counter, which always counts the mascot's 8 frames, so each
// drawing gets 4 ticks - the wave runs at half the mascot's rate, which is what
// makes it read as a wave rather than a twitch. `inverted` picks the day table.
static void render_snow(bool inverted) {
    oled_set_cursor(0, 0);
    if (inverted) {
        oled_write_raw_P(oled_snow_inv[oled_frame % SOFLE_SNOW_FRAMES], sizeof(oled_snow_inv[0]));
    } else {
        oled_write_raw_P(oled_snow[oled_frame % SOFLE_SNOW_FRAMES], sizeof(oled_snow[0]));
    }
}

// The screensaver itself: the sleeping mascot, on this half, over and over.
//
// Always the mascot, whatever screen you left it on: the snow pair has no
// sleeping drawing, and showing two awake snowboarders as a screensaver would
// be nonsense. It is the normal (lit-on-dark) polarity, not whatever inversion
// the display was left in, for the same reason a screensaver should look the
// same every time.
static void render_sleep(void) {
    oled_set_cursor(0, 0);
    oled_write_raw_P(oled_anim[SOFLE_ANIM_SLEEP][oled_frame], sizeof(oled_anim[0][0]));
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
    anim_advance_frame();
    wpm_history_sample();

    // The screensaver outranks everything else: it covers the boot animation
    // too, so a half that is left alone straight after power-up just goes to
    // sleep instead of hopping once and then freezing on a status screen.
    uint8_t want;
    if (oled_sleeping) {
        want = SOFLE_SCREEN_SLEEP;
    } else if (timer_elapsed32(oled_boot_time) < SOFLE_BOOT_MS) {
        want = SOFLE_SCREEN_BOOT;
    } else {
        want = oled_screen;
    }

    // Switching screens leaves the previous one's pixels behind - the status
    // screen only paints some of the rows, and the info screens fewer still
    // than the animations - so blank the buffer whenever the screen changes.
    static uint8_t drawn = 0xFF;
    if (drawn != want) {
        oled_clear();
        drawn = want;
    }

    if (want == SOFLE_SCREEN_SLEEP) {
        render_sleep();
    } else if (want == SOFLE_SCREEN_BOOT) {
        render_animation(0); // the hop is the "hello" one
    } else if (want == OLED_SCREEN_SNOW) {
        render_snow(false);
    } else if (want == OLED_SCREEN_SNOW_INV) {
        render_snow(true);
    } else if (want >= OLED_SCREEN_ANIM && want < OLED_SCREEN_ANIM_INV) {
        render_animation(want - OLED_SCREEN_ANIM);
    } else if (want >= OLED_SCREEN_ANIM_INV && want < OLED_SCREEN_SNOW) {
        render_animation_inv(want - OLED_SCREEN_ANIM_INV);
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

// Bump this whenever the *shape* of the keymap changes in a way that makes an
// existing EEPROM wrong: a layer moving, MO() pointing at a different layer,
// keys added or removed. VIA keeps the keymap in EEPROM and only seeds it from
// the firmware the first time, so without this check a reflash keeps the old
// layout and the layer keys end up switching the wrong layers. Each half
// checks its own EEPROM.
//
// 4：ADJUST 层加了灯光键（v3）之后又加了「纯白常亮」直达键，并把默认灯效
//    改成 solid_color / sat=0；版本一变顺手把 rgb_matrix 的 EEPROM 也刷回默认，
//    不然老机器上还亮着以前的 cycle_out_in。
// 5：ADJUST 层一度多过一个 SNOW_TOGG 键（切换动画图那套）。后来发现"用 OLED 键翻页"
//    才是顺手的用法，雪人改成 OLED 循环里的一个画面（见 oled_snow.h），那个键撤了——
//    所以 6 又刷一次，把两半 EEPROM 里遗留的那个键清掉。
#define SOFLE_EEPROM_VERSION 6

// Out of the box: pure white on both halves; the left OLED shows the status
// screen, the right one the first animation.
void keyboard_post_init_user(void) {
    oled_screen    = is_keyboard_left() ? OLED_SCREEN_STATUS : OLED_SCREEN_ANIM;
    oled_boot_time = timer_read32();
    // Start the screensaver's idle clock at power-up, so a keyboard nobody
    // touches still falls asleep SOFLE_SLEEP_MS in.
    last_activity  = oled_boot_time;

    // Both halves register: the slave's copy is the one the master calls.
    transaction_register_rpc(SOFLE_SCREENSAVER_SYNC, screensaver_sync_slave_handler);

#if defined(VIA_ENABLE)
    if (eeconfig_read_user() != SOFLE_EEPROM_VERSION) {
        dynamic_keymap_reset(); // re-seed the keymap and encoder map from the firmware
#ifdef RGB_MATRIX_ENABLE
        // 灯光设置（灯效/颜色/亮度）另外存在 rgb_matrix 那块 EEPROM 里，
        // 键位重置不会碰它，所以这里单独刷一次默认值：纯白常亮。
        eeconfig_update_rgb_matrix_default();
#endif
        eeconfig_update_user(SOFLE_EEPROM_VERSION);
    }
#endif
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

/* ------------------------------------------------------------------------
 * OLED screensaver ("sleeping zzz")
 *
 * The clock is last_activity; a local key press resets it and sets
 * saw_activity, the token that travels the split link. The master asks the
 * slave for its token every SOFLE_SLEEP_SYNC_MS and adds the answer to the same
 * clock, so it really measures "nobody typed on either half" - the two halves
 * therefore go to sleep on the same signal and cannot disagree about it.
 * Waking is the other way round and purely local: any key brings *that*
 * display back within a scan, with no round trip to wait for.
 *
 * The screensaver is a display state, not a selected screen: while it is up
 * the half keeps the screen it was on in oled_screen and goes straight back
 * to it, so falling asleep never costs you your chosen screen.
 * ------------------------------------------------------------------------ */

static bool oled_idle_expired(void) {
    return !saw_activity && !peer_activity && timer_elapsed32(last_activity) >= SOFLE_SLEEP_MS;
}

// Slave side of SOFLE_SCREENSAVER_SYNC: answer with whether this half has seen
// a key since the last time it was asked.
static void screensaver_sync_slave_handler(uint8_t in_buflen, const void *in_data, uint8_t out_buflen, void *out_data) {
    const sofle_activity_sync_t *m2s = (const sofle_activity_sync_t *)in_data;
    sofle_activity_sync_t       *s2m = (sofle_activity_sync_t *)out_data;

    // Consume our token and answer with it.
    bool mine    = saw_activity;
    saw_activity = false;

    if (m2s == NULL || s2m == NULL || in_buflen < sizeof(*m2s) || out_buflen < sizeof(*s2m)) {
        saw_activity = mine; // malformed exchange: put the token back and be asked again
        return;
    }

    s2m->saw_activity = mine;

    // The master's own token arrives in the same call, so the slave can judge
    // "did anyone type?" exactly like the master does.
    peer_activity = m2s->saw_activity;
    if (peer_activity) {
        last_activity = timer_read32();
    }
}

// Master side: only the master talks to the slave, and only every
// SOFLE_SLEEP_SYNC_MS, so the wire is not carrying this on every scan.
static void screensaver_sync_master(void) {
    static uint32_t last_sync;

    uint32_t now_ms = timer_read32();
    if (timer_elapsed32(last_sync) < SOFLE_SLEEP_SYNC_MS) {
        return;
    }

    sofle_activity_sync_t m2s = {.saw_activity = saw_activity ? 1 : 0};
    sofle_activity_sync_t s2m = {0};

    if (!transaction_rpc_exec(SOFLE_SCREENSAVER_SYNC, sizeof(m2s), &m2s, sizeof(s2m), &s2m)) {
        // Torn exchange: the token is simply answered again next period, which
        // errs towards keeping both displays awake rather than sleeping apart.
        return;
    }

    saw_activity = false;
    last_sync    = now_ms;

    peer_activity = s2m.saw_activity;
    if (peer_activity) {
        last_activity = now_ms; // the other half typed, so this half stays up too
    }
}

void housekeeping_task_user(void) {
    static matrix_row_t last[MATRIX_ROWS_PER_HAND];
    static uint8_t      held_row = 0xFF, held_col;
    static uint32_t     last_advance;

    bool     active = false;
    uint32_t now_ms = timer_read32();

    for (uint8_t i = 0; i < MATRIX_ROWS_PER_HAND; i++) {
        uint8_t      row = is_keyboard_left() ? i : i + MATRIX_ROWS_PER_HAND;
        matrix_row_t now = matrix_get_row(row);
        matrix_row_t hit = now & ~last[i];
        last[i]          = now;

        if (hit) {
            active = true; // any key of this half: typing or not, it counts
        }

        while (hit) {
            uint8_t col = __builtin_ctz(hit);
            hit &= hit - 1;

            if (oled_switch_key(row, col)) {
                oled_screen  = (oled_screen + 1) % OLED_SCREEN_COUNT;
                held_row     = row;
                held_col     = col;
                last_advance = now_ms;
            } else {
                key_count++; // the display key is not typing
            }
        }
    }

    // A key went down: this half is awake again, and so is the other one once
    // the token reaches it. The screensaver does not swallow the key - it does
    // whatever it normally does, the display just comes back to its screen.
    if (active) {
        last_activity = now_ms;
        saw_activity  = true;
        oled_sleeping = false;
    } else if (!oled_sleeping && oled_idle_expired()) {
        oled_sleeping = true;
    }

    // The split exchange, before the screen is drawn so this scan's answer is
    // already accounted for. Only the master runs it; the slave is the one
    // being asked.
    if (is_keyboard_master()) {
        screensaver_sync_master();
    }

    // Keep advancing while the key is held, so walking through a dozen screens
    // is one press and a wait rather than a dozen taps.
    if (held_row != 0xFF) {
        if (!matrix_is_on(held_row, held_col)) {
            held_row = 0xFF;
        } else if (timer_elapsed32(last_advance) >= SOFLE_OLED_HOLD_MS) {
            oled_screen  = (oled_screen + 1) % OLED_SCREEN_COUNT;
            last_advance = now_ms;
        }
    }
}

#endif

layer_state_t layer_state_set_user(layer_state_t state) {
    return update_tri_layer_state(state, _LOWER, _RAISE, _ADJUST);
}

#ifdef RGB_MATRIX_ENABLE
/* 灯效直达键的公共部分：切到指定灯效，并顺手把灯打开——关了灯再按预设键
 * 却什么都不亮，会让人以为是键坏了。两个都是 noeeprom 版本，只动 RAM：
 * 重启后仍回到 EEPROM 里的灯效，也不会把 VIA Lighting 页的设置顶掉。 */
static void fx_select(uint8_t mode) {
    rgb_matrix_enable_noeeprom();
    rgb_matrix_mode_noeeprom(mode);
}
#endif

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case OLED_NEXT:
            // Not handled here: only the master sees keycodes, and both halves
            // need to switch, so housekeeping_task_user() picks this up on the
            // half the key actually sits on. Swallow it so nothing else sees it.
            return false;
#ifdef RGB_MATRIX_ENABLE
        /* 灯效直达（ADJUST 层 row3 左边 4~5 列 × 左右两半）。每个灯效外面套一层
         * ENABLE_ 宏：#ifdef 关掉某个灯效时这里跟着失效，而不是编译报错。 */
        case FX_WHITE:
            /* 纯白常亮（出厂默认）：把饱和度归零就是白，色相随它去；亮度也回到出厂值
             * （RGB_MATRIX_DEFAULT_VAL = 127），这样一个键就是「恢复出厂灯效」，
             * 不会出现「之前把亮度拧到 0，按了纯白却什么都没亮」。
             * solid_color 这个灯效没有 ENABLE_ 开关，永远编在固件里，所以不用 #ifdef。 */
            if (record->event.pressed) {
                rgb_matrix_enable_noeeprom(); // 必须在 sethsv 之前：关着灯时 sethsv 是空操作
                rgb_matrix_sethsv_noeeprom(0, 0, RGB_MATRIX_DEFAULT_VAL);
                rgb_matrix_mode_noeeprom(RGB_MATRIX_SOLID_COLOR);
            }
            return false;
        case FX_CYCLE_OUT_IN:
#    if defined(ENABLE_RGB_MATRIX_CYCLE_OUT_IN)
            if (record->event.pressed) fx_select(RGB_MATRIX_CYCLE_OUT_IN);
#    endif
            return false;
        case FX_HUE_WAVE:
#    if defined(ENABLE_RGB_MATRIX_HUE_WAVE)
            if (record->event.pressed) fx_select(RGB_MATRIX_HUE_WAVE);
#    endif
            return false;
        case FX_RAINBOW_BEACON:
#    if defined(ENABLE_RGB_MATRIX_RAINBOW_BEACON)
            if (record->event.pressed) fx_select(RGB_MATRIX_RAINBOW_BEACON);
#    endif
            return false;
        case FX_PIXEL_FLOW:
#    if defined(ENABLE_RGB_MATRIX_PIXEL_FLOW)
            if (record->event.pressed) fx_select(RGB_MATRIX_PIXEL_FLOW);
#    endif
            return false;
        case FX_JELLYBEAN:
#    if defined(ENABLE_RGB_MATRIX_JELLYBEAN_RAINDROPS)
            if (record->event.pressed) fx_select(RGB_MATRIX_JELLYBEAN_RAINDROPS);
#    endif
            return false;
        case FX_DIGITAL_RAIN:
#    if defined(ENABLE_RGB_MATRIX_DIGITAL_RAIN)
            if (record->event.pressed) fx_select(RGB_MATRIX_DIGITAL_RAIN);
#    endif
            return false;
        case FX_REACTIVE_NEXUS:
#    if defined(ENABLE_RGB_MATRIX_SOLID_REACTIVE_MULTINEXUS)
            if (record->event.pressed) fx_select(RGB_MATRIX_SOLID_REACTIVE_MULTINEXUS);
#    endif
            return false;
        case FX_TYPING_HEATMAP:
#    if defined(ENABLE_RGB_MATRIX_TYPING_HEATMAP)
            if (record->event.pressed) fx_select(RGB_MATRIX_TYPING_HEATMAP);
#    endif
            return false;
#endif // RGB_MATRIX_ENABLE
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
 * 例外是 ADJUST(3)：旋钮在这一层临时变成调灯——左旋钮亮度、右旋钮灯效速度
 * （和 ADJUST 层 row0 上那几个 RM_* 键是同一组功能）。
 *
 * If a knob turns the wrong way, swap the two keycodes in its pair.
 * ------------------------------------------------------------------------ */

#ifdef ENCODER_MAP_ENABLE
    const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][NUM_DIRECTIONS] = {
        //        left knob                        right knob
       [0] = { ENCODER_CCW_CW(KC_VOLD, KC_VOLU),   ENCODER_CCW_CW(KC_MPRV, KC_MNXT) },
       [1] = { ENCODER_CCW_CW(_______, _______),  ENCODER_CCW_CW(_______, _______) },
       [2] = { ENCODER_CCW_CW(_______, _______),  ENCODER_CCW_CW(_______, _______) },
       [3] = { ENCODER_CCW_CW(RM_VALD, RM_VALU),   ENCODER_CCW_CW(RM_SPDD, RM_SPDU) },
      };
#endif

