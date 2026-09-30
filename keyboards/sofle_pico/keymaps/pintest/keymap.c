// Copyright 2026
// SPDX-License-Identifier: GPL-2.0-or-later
//
// DIAGNOSTIC KEYMAP - electrical self test of the matrix pins.
//
// This answers "is the Pico's pin itself bad?" without needing a multimeter.
// Every matrix pin is exercised three ways while the console prints the result:
//
//   up=1   input with pull-up   -> 0 means the line is being held low
//   down=0 input with pull-down -> 1 means the line is being held high
//   low=0  driving low (push-pull, a few microseconds), read back -> 1 means
//          the pin cannot sink, or the line is being pulled high hard
//
// The last block drives one pin low at a time and reads every other pin, so a
// solder bridge (or a short on the PCB) shows up as a pair.
//
// A pin that fails here is a suspect even with the keyboard unplugged from the
// PCB (socketed Pico): the same test runs with the Pico alone on USB, where
// nothing else can pull the line - there the only things left are the pin and
// the solder joint.
//
// Only one pin is ever driven, and every other pin is left as a high impedance
// input while it happens, so nothing pushes against anything else.

#include QMK_KEYBOARD_H
#include "gpio.h"

// MATRIX_COL_PINS / MATRIX_ROW_PINS come from keyboard.json; the names are
// spelled out here so the console output can be read without the schematic.
static const pin_t test_cols[] = MATRIX_COL_PINS;
static const pin_t test_rows[] = MATRIX_ROW_PINS;
static const char *col_names[] = {"col0 GP1 ", "col1 GP2 ", "col2 GP3 ", "col3 GP4 ", "col4 GP5 ", "col5 GP8 "};
static const char *row_names[] = {"row0 GP9 ", "row1 GP10", "row2 GP11", "row3 GP12", "row4 GP13"};

#define NCOLS (sizeof(test_cols) / sizeof(test_cols[0]))
#define NROWS (sizeof(test_rows) / sizeof(test_rows[0]))
#define TEST_PIN_COUNT (NCOLS + NROWS)

static pin_t pin_at(uint8_t i) {
    return i < NCOLS ? test_cols[i] : test_rows[i - NCOLS];
}
static const char *name_at(uint8_t i) {
    return i < NCOLS ? col_names[i] : row_names[i - NCOLS];
}
#define TEST_INTERVAL_MS 5000

static void pin_test(void) {
    uprintf("--- sofle_pico pin test, this half is %s ---\n", is_keyboard_left() ? "left" : "right");

    for (uint8_t i = 0; i < TEST_PIN_COUNT; i++) {
        pin_t pin = pin_at(i);

        gpio_set_pin_input_high(pin);
        wait_us(50);
        uint8_t up = gpio_read_pin(pin);

        gpio_set_pin_input_low(pin);
        wait_us(50);
        uint8_t down = gpio_read_pin(pin);

        gpio_set_pin_output(pin);
        gpio_write_pin_low(pin);
        wait_us(50);
        uint8_t low = gpio_read_pin(pin);

        gpio_set_pin_input_high(pin); // leave it safe for the scanner

        const char *verdict = "OK";
        if (!up && !low) {
            verdict = "BAD: line held low (short to GND, or dead pin)";
        } else if (up && down) {
            verdict = "BAD: line held high (short to 3V3)";
        } else if (low) {
            verdict = "BAD: cannot sink (dead pin)";
        } else if (!up) {
            verdict = "odd: low with pull-up but not with pull-down";
        }
        uprintf("%s  up=%u down=%u low=%u  %s\n", name_at(i), up, down, low, verdict);
        wait_us(50);
    }

    // Who is bridged to whom: pull one line low, every other line must stay high.
    bool found = false;
    for (uint8_t i = 0; i < TEST_PIN_COUNT; i++) {
        for (uint8_t j = 0; j < TEST_PIN_COUNT; j++) {
            if (i != j) {
                gpio_set_pin_input_high(pin_at(j));
            }
        }
        gpio_set_pin_output(pin_at(i));
        gpio_write_pin_low(pin_at(i));
        wait_us(50);
        for (uint8_t j = 0; j < TEST_PIN_COUNT; j++) {
            if (i != j && !gpio_read_pin(pin_at(j))) {
                uprintf("BRIDGE: %s <-> %s\n", name_at(i), name_at(j));
                found = true;
            }
        }
        gpio_set_pin_input_high(pin_at(i));
        wait_us(50);
    }
    if (!found) {
        uprintf("no bridges between matrix pins\n");
    }
    uprintf("--- end ---\n");
}

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT(
    KC_A, KC_B, KC_C, KC_D, KC_E, KC_F, S(KC_F), S(KC_E), S(KC_D), S(KC_C), S(KC_B), S(KC_A),
    KC_G, KC_H, KC_I, KC_J, KC_K, KC_L, S(KC_L), S(KC_K), S(KC_J), S(KC_I), S(KC_H), S(KC_G),
    KC_M, KC_N, KC_O, KC_P, KC_Q, KC_R, S(KC_R), S(KC_Q), S(KC_P), S(KC_O), S(KC_N), S(KC_M),
    KC_S, KC_T, KC_U, KC_V, KC_W, KC_X, KC_4, KC_8, S(KC_X), S(KC_W), S(KC_V), S(KC_U),
    S(KC_T), S(KC_S), KC_Y, KC_Z, KC_1, KC_2, KC_3, KC_7, KC_6, KC_5, S(KC_Z), S(KC_Y)
    ),
};


void keyboard_post_init_user(void) {
    // Let the host's console attach before the first run.
    wait_ms(1500);
    pin_test();
    matrix_init(); // put the pins back the way the scanner expects them
}

void housekeeping_task_user(void) {
    static uint32_t last = 0;
    if (timer_elapsed32(last) > TEST_INTERVAL_MS) {
        last = timer_read32();
        pin_test();
        matrix_init();
    }
}
