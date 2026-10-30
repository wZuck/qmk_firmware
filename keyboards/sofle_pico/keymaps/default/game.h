// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <stdbool.h>
#include <stdint.h>

enum game_action {
    GAME_ACTION_CONFIRM,
    GAME_ACTION_PAUSE,
    GAME_ACTION_RESTART,
    GAME_ACTION_EXIT,
    GAME_ACTION_LEFT,
    GAME_ACTION_RIGHT,
    GAME_ACTION_DOWN,
    GAME_ACTION_ROTATE,
    GAME_ACTION_DROP,
};

void game_init(void);
void game_stop(void);
bool game_handle_action(enum game_action action);
void game_housekeeping(bool game_layer_active);
bool game_oled_task(bool game_layer_active);
