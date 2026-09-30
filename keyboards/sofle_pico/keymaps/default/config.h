// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

/* ------------------------------------------------------------------------
 * Both halves draw their own OLED, and the left half draws the status screen
 * no matter which half the USB cable is in. When the left half is the slave,
 * the layer, the host LED state and the typing speed all have to be mirrored
 * over the split link or that screen would sit frozen on stale data.
 *
 * Keep this here rather than in the keyboard's config.h: the keyboard only
 * enables the layer mirror when RGB_MATRIX_ENABLE is on, and the status
 * screen should not depend on RGB being built in.
 * ------------------------------------------------------------------------ */

#define SPLIT_LAYER_STATE_ENABLE
#define SPLIT_LED_STATE_ENABLE
#define SPLIT_WPM_ENABLE

/* ------------------------------------------------------------------------
 * VIA's "Key Tester" is driven by the live matrix state over raw HID, and QMK
 * answers that request with zeroes unless VIA_INSECURE is defined - that is
 * why the tester shows nothing while the keyboard types perfectly well.
 *
 * The trade-off is real: with this on, any program that can talk raw HID can
 * read which keys are down (the build prints a keylogger warning). Delete the
 * line if you would rather not expose that; everything else in VIA (remapping,
 * macros, lighting) keeps working either way.
 * ------------------------------------------------------------------------ */

#define VIA_INSECURE
