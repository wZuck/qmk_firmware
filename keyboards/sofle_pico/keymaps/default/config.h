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
 * The OLED screensaver has to be agreed on by both halves - they go to sleep
 * together and wake together - and the split has no built-in transaction for
 * that. The one user slot QMK reserves for exactly this is enough: keymap.c
 * uses it to ask the slave half "did you see a key this epoch?" (see
 * SOFLE_SCREENSAVER_SYNC there).
 *
 * This is a user-level define rather than a keyboard-level one on purpose:
 * only this keymap's OLED cares, and the probe/pintest/debug keymaps should
 * not pay for the extra transaction.
 * ------------------------------------------------------------------------ */

#define SPLIT_TRANSACTION_IDS_USER SOFLE_SCREENSAVER_SYNC

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
