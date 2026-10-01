/* AUTO-GENERATED -- DO NOT EDIT.
 *
 * Host-compatible copy of
 *   quantum/rgb_matrix/animations/pixel_flow_anim.h
 * produced by build_soflepico/led_effects/prepare_effects.py.
 *
 * Change applied:
 *   the block-scope (GCC nested) function `interval()` on line 17 (inside `static bool PIXEL_FLOW(effect_params_t* params) {`) was hoisted verbatim to file scope as `static`; clang rejects nested function definitions. Pure move, verified.
 *
 * Run `python3 prepare_effects.py --show-diff` to see the exact difference, and
 * `--check` to re-verify it against the current QMK sources.
 */

// Copyright 2022 @filterpaper
// SPDX-License-Identifier: GPL-2.0+

#ifdef ENABLE_RGB_MATRIX_PIXEL_FLOW
RGB_MATRIX_EFFECT(PIXEL_FLOW)
#    ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS

static uint32_t interval(void) {
        return 3000 / scale16by8(qadd8(rgb_matrix_config.speed, 16), 16);
}

static bool PIXEL_FLOW(effect_params_t* params) {
    // LED state array
    static rgb_t led[RGB_MATRIX_LED_COUNT];

    static uint32_t wait_timer = 0;
    if (wait_timer > g_rgb_timer) {
        return false;
    }


    if (params->init) {
        // Clear LEDs and fill the state array
        rgb_matrix_set_color_all(0, 0, 0);
        for (uint8_t j = 0; j < RGB_MATRIX_LED_COUNT; ++j) {
            led[j] = (random8() & 2) ? (rgb_t){0, 0, 0} : rgb_matrix_hsv_to_rgb((hsv_t){random8(), random8_min_max(127, 255), rgb_matrix_config.hsv.v});
        }
    }

    RGB_MATRIX_USE_LIMITS(led_min, led_max);
    // Light LEDs based on state array
    for (uint8_t i = led_min; i < led_max; ++i) {
        RGB_MATRIX_TEST_LED_FLAGS();
        rgb_matrix_set_color(i, led[i].r, led[i].g, led[i].b);
    }

    if (!rgb_matrix_check_finished_leds(led_max)) {
        // Shift LED state forward
        for (uint8_t j = 0; j < led_max - 1; ++j) {
            led[j] = led[j + 1];
        }
        // Fill last LED
        led[led_max - 1] = (random8() & 2) ? (rgb_t){0, 0, 0} : rgb_matrix_hsv_to_rgb((hsv_t){random8(), random8_min_max(127, 255), rgb_matrix_config.hsv.v});
        // Set pulse timer
        wait_timer = g_rgb_timer + interval();
    }

    return rgb_matrix_check_finished_leds(led_max);
}

#    endif // RGB_MATRIX_CUSTOM_EFFECT_IMPLS
#endif     // ENABLE_RGB_MATRIX_PIXEL_FLOW
