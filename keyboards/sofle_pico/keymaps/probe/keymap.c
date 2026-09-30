// Copyright 2026
// SPDX-License-Identifier: GPL-2.0-or-later
//
// DIAGNOSTIC KEYMAP - not for daily use.
//
// Every matrix position types one unique character, so it is obvious which
// keys register at all and whether the halves are the right way round:
//
//   left half  (matrix rows 0-4) -> lowercase a-z, then 1 2 3 4
//   right half (matrix rows 5-9) -> uppercase A-Z, then 5 6 7 8
//
// Pressing a key on the left half and getting an uppercase letter means that
// half is being taken for the right half (EE_HANDS handedness). A key that
// types nothing is a matrix position that is not registering - readme.md has
// the row/column table.
//
// VIA is off in this build, so the characters come straight from this file
// and whatever is in EEPROM cannot confuse the result.

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
