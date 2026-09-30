// Copyright 2026
// SPDX-License-Identifier: GPL-2.0-or-later
//
// DIAGNOSTIC KEYMAP - dumps the raw matrix over the USB console.
//
// Plug the USB cable into the half you want to test: that half is the master,
// so this shows *its own* matrix rather than what arrives over the split link.
// Run `qmk console`, then press keys one at a time. Every edge of every matrix
// position prints one line:
//
//     DOWN r2 c4      a key going down at row 2, column 4
//     UP   r2 c4      and back up
//
// The keys also type the probe characters (lowercase on the left half,
// uppercase on the right) so you can watch the same thing in a text editor.
//
// Columns are GP1 GP2 GP3 GP4 GP5 GP8 = c0..c5, rows are GP9 GP10 GP11 GP12
// GP13 = r0..r4 on the left half, and r5..r9 on the right half.

#include QMK_KEYBOARD_H

void keyboard_post_init_user(void) {
    uprintf("sofle_pico debug build, this half is %s\n", is_keyboard_left() ? "left" : "right");
}

void matrix_scan_user(void) {
    static matrix_row_t last[MATRIX_ROWS];
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
        matrix_row_t now = matrix_get_row(r);
        if (now == last[r]) {
            continue;
        }
        for (uint8_t c = 0; c < MATRIX_COLS; c++) {
            bool was = last[r] & ((matrix_row_t)1 << c);
            bool is  = now & ((matrix_row_t)1 << c);
            if (was != is) {
                uprintf("%s r%u c%u\n", is ? "DOWN" : "UP  ", r, c);
            }
        }
        last[r] = now;
    }
}

#include QMK_KEYBOARD_H

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT(
    KC_A, KC_B, KC_C, KC_D, KC_E, KC_F, S(KC_F), S(KC_E), S(KC_D), S(KC_C), S(KC_B), S(KC_A),
    KC_G, KC_H, KC_I, KC_J, KC_K, KC_L, S(KC_L), S(KC_K), S(KC_J), S(KC_I), S(KC_H), S(KC_G),
    KC_M, KC_N, KC_O, KC_P, KC_Q, KC_R, S(KC_R), S(KC_Q), S(KC_P), S(KC_O), S(KC_N), S(KC_M),
    KC_S, KC_T, KC_U, KC_V, KC_W, KC_X, KC_4, KC_8, S(KC_X), S(KC_W), S(KC_V), S(KC_U),
    S(KC_T), S(KC_S), KC_Y, KC_Z, KC_1, KC_2, KC_3, KC_7, KC_6, KC_5, S(KC_Z), S(KC_Y)
    ),
};
