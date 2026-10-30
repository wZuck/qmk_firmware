// SPDX-License-Identifier: GPL-2.0-or-later

#include "game.h"

#include <string.h>

#include "quantum.h"
#include "timer.h"
#ifdef SPLIT_KEYBOARD
#    include "transactions.h"
#endif
#ifdef OLED_ENABLE
#    include "oled_driver.h"
#endif

enum game_kind {
    GAME_NONE,
    GAME_SNAKE,
    GAME_TETRIS,
};

enum game_status {
    GAME_STATUS_RUNNING,
    GAME_STATUS_PAUSED,
    GAME_STATUS_OVER,
};

#define GAME_SYNC_MAGIC 0x5A
#define GAME_SYNC_VERSION 2
#define GAME_RPC_INTERVAL_MS 20

#define GAME_TETRIS_WIDTH 10
#define GAME_TETRIS_HEIGHT 20
#define GAME_TETRIS_FULL_ROW 0x03FF
#define GAME_TETRIS_CELL_SIZE 6

#define GAME_SNAKE_WIDTH 16
#define GAME_SNAKE_HEIGHT 31
#define GAME_SNAKE_CELLS (GAME_SNAKE_WIDTH * GAME_SNAKE_HEIGHT)
#define GAME_SNAKE_START_LENGTH 3

/* The game uses the same 64 x 128 portrait orientation as the normal screens. */
#define GAME_CANVAS_WIDTH 64
#define GAME_CANVAS_HEIGHT 128
#define GAME_CANVAS_SIZE (GAME_CANVAS_WIDTH * GAME_CANVAS_HEIGHT / 8)

typedef struct __attribute__((packed)) {
    uint8_t  magic;
    uint8_t  version;
    uint8_t  request_seq;
    uint8_t  request_action; // zero means no action, otherwise action + 1
    uint8_t  game_layer_active;
    uint8_t  game;
    uint8_t  status;
    uint8_t  menu_selection;
    uint16_t score;
    uint8_t  level;
    uint8_t  lines;
    uint8_t  next_kind;
    uint8_t  piece_kind;
    uint8_t  rotation;
    int8_t   piece_x;
    int8_t   piece_y;
    uint8_t  direction;
    uint16_t snake_length;
    uint8_t  food_x;
    uint8_t  food_y;
    uint8_t  head_x;
    uint8_t  head_y;
    uint8_t  cells[64];
} game_sync_t;

typedef struct {
    uint8_t  kind;
    uint8_t  status;
    uint8_t  menu_selection;
    uint16_t score;
    uint8_t  level;
    uint8_t  lines;
    uint8_t  next_kind;
    uint8_t  piece_kind;
    uint8_t  rotation;
    int8_t   piece_x;
    int8_t   piece_y;
    uint16_t board[GAME_TETRIS_HEIGHT];

    uint8_t  direction;
    uint8_t  next_direction;
    uint16_t snake_length;
    uint16_t snake_body[GAME_SNAKE_CELLS];
    uint16_t food;

    uint32_t last_tick;
    uint32_t rng;
    uint8_t  bag[7];
    uint8_t  bag_pos;
} game_state_t;

static game_state_t game;
static game_sync_t  game_view;
static bool         game_dirty;
static bool         game_last_sent_active;
static uint32_t     game_last_exchange;
static uint8_t      game_request_seq;
static uint8_t      game_last_received_seq;

typedef struct {
    uint8_t action;
    uint8_t seq;
} game_queued_action_t;

static game_queued_action_t game_action_queue[8];
static uint8_t              game_action_head;
static uint8_t              game_action_count;

static const uint16_t tetrominoes[7][4] = {
    {0x0F00, 0x2222, 0x00F0, 0x4444}, // I
    {0x0660, 0x0660, 0x0660, 0x0660}, // O
    {0x7200, 0x2620, 0x2700, 0x4640}, // T
    {0x6C00, 0x4620, 0x6C00, 0x4620}, // S
    {0xC600, 0x2640, 0xC600, 0x2640}, // Z
    {0x8E00, 0xC880, 0xE200, 0x44C0}, // J
    {0x2E00, 0x88C0, 0xE800, 0xC440}, // L
};

STATIC_ASSERT(sizeof(game_sync_t) <= RPC_M2S_BUFFER_SIZE, "the game packet must fit the master-to-slave buffer");
STATIC_ASSERT(sizeof(game_sync_t) <= RPC_S2M_BUFFER_SIZE, "the game packet must fit the slave-to-master buffer");
STATIC_ASSERT(GAME_SNAKE_CELLS <= 64 * 8, "the snake grid must fit the packed RPC cells");
STATIC_ASSERT(GAME_TETRIS_WIDTH *GAME_TETRIS_CELL_SIZE <= GAME_CANVAS_WIDTH - 4, "the Tetris board must fit the portrait canvas");
STATIC_ASSERT(GAME_TETRIS_HEIGHT *GAME_TETRIS_CELL_SIZE <= GAME_CANVAS_HEIGHT - 8, "the Tetris board must fit the portrait canvas");

static bool game_on_right(void) {
    return !is_keyboard_left();
}

static bool game_mask_cell(uint16_t mask, uint8_t row, uint8_t col) {
    return mask & ((uint16_t)0x8000 >> (row * 4 + col));
}

static uint32_t game_random(void) {
    uint32_t value = game.rng;
    value ^= value << 13;
    value ^= value >> 17;
    value ^= value << 5;
    game.rng = value ? value : 0xA341316C;
    return game.rng;
}

static void game_seed_random(void) {
    game.rng = timer_read32() ^ 0x9E3779B9;
    if (!game.rng) {
        game.rng = 0xA341316C;
    }
}

static void game_fill_bag(void) {
    for (uint8_t i = 0; i < 7; i++) {
        game.bag[i] = i;
    }
    for (uint8_t i = 6; i > 0; i--) {
        uint8_t j   = game_random() % (i + 1);
        uint8_t tmp = game.bag[i];
        game.bag[i] = game.bag[j];
        game.bag[j] = tmp;
    }
    game.bag_pos = 0;
}

static uint8_t game_next_from_bag(void) {
    if (game.bag_pos >= 7) {
        game_fill_bag();
    }
    return game.bag[game.bag_pos++];
}

static uint16_t game_tetromino_mask(uint8_t kind, uint8_t rotation) {
    return tetrominoes[kind % 7][rotation & 3];
}

static bool game_tetris_can_place(uint8_t kind, uint8_t rotation, int8_t x, int8_t y) {
    uint16_t mask = game_tetromino_mask(kind, rotation);
    for (uint8_t row = 0; row < 4; row++) {
        for (uint8_t col = 0; col < 4; col++) {
            if (!game_mask_cell(mask, row, col)) {
                continue;
            }
            int8_t board_x = x + col;
            int8_t board_y = y + row;
            if (board_x < 0 || board_x >= GAME_TETRIS_WIDTH || board_y >= GAME_TETRIS_HEIGHT) {
                return false;
            }
            if (board_y >= 0 && (game.board[board_y] & ((uint16_t)1 << board_x))) {
                return false;
            }
        }
    }
    return true;
}

static void game_tetris_spawn(void) {
    game.piece_kind = game.next_kind;
    game.next_kind  = game_next_from_bag();
    game.rotation   = 0;
    game.piece_x    = 3;
    game.piece_y    = -1;
    if (!game_tetris_can_place(game.piece_kind, game.rotation, game.piece_x, game.piece_y)) {
        game.status = GAME_STATUS_OVER;
    }
}

static void game_tetris_start(void) {
    game.kind   = GAME_TETRIS;
    game.status = GAME_STATUS_RUNNING;
    game.score  = 0;
    game.level  = 1;
    game.lines  = 0;
    memset(game.board, 0, sizeof(game.board));
    game_fill_bag();
    game.next_kind = game_next_from_bag();
    game_tetris_spawn();
    game.last_tick = timer_read32();
}

static void game_add_score(uint16_t points) {
    uint32_t score = (uint32_t)game.score + points;
    game.score     = score > UINT16_MAX ? UINT16_MAX : score;
}

static uint8_t game_tetris_clear_lines(void) {
    uint8_t cleared = 0;
    for (int8_t row = GAME_TETRIS_HEIGHT - 1; row >= 0; row--) {
        if (game.board[row] != GAME_TETRIS_FULL_ROW) {
            continue;
        }
        for (int8_t dst = row; dst > 0; dst--) {
            game.board[dst] = game.board[dst - 1];
        }
        game.board[0] = 0;
        cleared++;
        row++;
    }
    return cleared;
}

static void game_tetris_lock_piece(void) {
    uint16_t mask = game_tetromino_mask(game.piece_kind, game.rotation);
    for (uint8_t row = 0; row < 4; row++) {
        for (uint8_t col = 0; col < 4; col++) {
            if (!game_mask_cell(mask, row, col)) {
                continue;
            }
            int8_t board_x = game.piece_x + col;
            int8_t board_y = game.piece_y + row;
            if (board_y < 0) {
                game.status = GAME_STATUS_OVER;
                return;
            }
            game.board[board_y] |= (uint16_t)1 << board_x;
        }
    }

    uint8_t cleared = game_tetris_clear_lines();
    if (cleared) {
        static const uint16_t points[5] = {0, 100, 300, 500, 800};
        game_add_score(points[cleared] * game.level);
        game.lines += cleared;
        game.level = 1 + game.lines / 10;
        if (game.level > 20) {
            game.level = 20;
        }
    }
    game_tetris_spawn();
}

static void game_tetris_move(int8_t dx, int8_t dy) {
    if (game.status != GAME_STATUS_RUNNING) {
        return;
    }
    if (game_tetris_can_place(game.piece_kind, game.rotation, game.piece_x + dx, game.piece_y + dy)) {
        game.piece_x += dx;
        game.piece_y += dy;
        game_dirty = true;
    } else if (dy > 0) {
        game_tetris_lock_piece();
        game_dirty = true;
    }
}

static void game_tetris_rotate(void) {
    if (game.status != GAME_STATUS_RUNNING) {
        return;
    }
    static const int8_t kicks[]  = {0, -1, 1, -2, 2};
    uint8_t             rotation = (game.rotation + 1) & 3;
    for (uint8_t i = 0; i < ARRAY_SIZE(kicks); i++) {
        int8_t x = game.piece_x + kicks[i];
        if (game_tetris_can_place(game.piece_kind, rotation, x, game.piece_y)) {
            game.rotation = rotation;
            game.piece_x  = x;
            game_dirty    = true;
            return;
        }
    }
}

static void game_tetris_hard_drop(void) {
    if (game.status != GAME_STATUS_RUNNING) {
        return;
    }
    while (game_tetris_can_place(game.piece_kind, game.rotation, game.piece_x, game.piece_y + 1)) {
        game.piece_y++;
        game_add_score(2);
    }
    game_tetris_lock_piece();
    game.last_tick = timer_read32();
    game_dirty     = true;
}

static uint16_t game_snake_cell(uint8_t x, uint8_t y) {
    return (uint16_t)y * GAME_SNAKE_WIDTH + x;
}

static uint8_t game_snake_x(uint16_t cell) {
    return cell % GAME_SNAKE_WIDTH;
}

static uint8_t game_snake_y(uint16_t cell) {
    return cell / GAME_SNAKE_WIDTH;
}

static bool game_snake_body_at(uint16_t cell, uint16_t count) {
    for (uint16_t i = 0; i < count; i++) {
        if (game.snake_body[i] == cell) {
            return true;
        }
    }
    return false;
}

static void game_snake_spawn_food(void) {
    if (game.snake_length >= GAME_SNAKE_CELLS) {
        game.status = GAME_STATUS_OVER;
        return;
    }
    uint16_t free_cells = GAME_SNAKE_CELLS - game.snake_length;
    uint16_t target     = game_random() % free_cells;
    for (uint16_t cell = 0; cell < GAME_SNAKE_CELLS; cell++) {
        if (game_snake_body_at(cell, game.snake_length)) {
            continue;
        }
        if (!target) {
            game.food = cell;
            return;
        }
        target--;
    }
}

static void game_snake_start(void) {
    game.kind           = GAME_SNAKE;
    game.status         = GAME_STATUS_RUNNING;
    game.score          = 0;
    game.direction      = 1;
    game.next_direction = 1;
    game.snake_length   = GAME_SNAKE_START_LENGTH;
    uint8_t head_x      = GAME_SNAKE_WIDTH / 2;
    uint8_t head_y      = GAME_SNAKE_HEIGHT / 2;
    for (uint8_t i = 0; i < GAME_SNAKE_START_LENGTH; i++) {
        game.snake_body[i] = game_snake_cell(head_x - i, head_y);
    }
    game_snake_spawn_food();
    game.last_tick = timer_read32();
}

static void game_snake_turn(uint8_t direction) {
    if (game.status != GAME_STATUS_RUNNING) {
        return;
    }
    if (direction == game.direction || (direction + 2) % 4 == game.direction) {
        return;
    }
    game.next_direction = direction;
}

static void game_snake_tick(uint32_t now) {
    uint16_t interval = 150 - (game.score / 10) * 3;
    if (interval < 60) {
        interval = 60;
    }
    if (timer_elapsed32(game.last_tick) < interval) {
        return;
    }
    game.last_tick = now;
    game.direction = game.next_direction;

    uint16_t head = game.snake_body[0];
    int16_t  x    = game_snake_x(head);
    int16_t  y    = game_snake_y(head);
    switch (game.direction) {
        case 0:
            y--;
            break;
        case 1:
            x++;
            break;
        case 2:
            y++;
            break;
        default:
            x--;
            break;
    }

    if (x < 0 || x >= GAME_SNAKE_WIDTH || y < 0 || y >= GAME_SNAKE_HEIGHT) {
        game.status = GAME_STATUS_OVER;
        game_dirty  = true;
        return;
    }

    uint16_t next      = game_snake_cell(x, y);
    bool     eating    = next == game.food;
    uint16_t check_len = game.snake_length - (eating ? 0 : 1);
    if (game_snake_body_at(next, check_len)) {
        game.status = GAME_STATUS_OVER;
        game_dirty  = true;
        return;
    }

    if (eating && game.snake_length < GAME_SNAKE_CELLS) {
        for (uint16_t i = game.snake_length; i > 0; i--) {
            game.snake_body[i] = game.snake_body[i - 1];
        }
        game.snake_length++;
    } else {
        for (uint16_t i = game.snake_length - 1; i > 0; i--) {
            game.snake_body[i] = game.snake_body[i - 1];
        }
    }
    game.snake_body[0] = next;

    if (eating) {
        game_add_score(10);
        game_snake_spawn_food();
    }
    game_dirty = true;
}

static void game_start(uint8_t kind) {
    memset(&game, 0, sizeof(game));
    game_seed_random();
    game.status = GAME_STATUS_RUNNING;
    if (kind == GAME_SNAKE) {
        game_snake_start();
    } else {
        game_tetris_start();
    }
    game_dirty = true;
}

void game_stop(void) {
    memset(&game, 0, sizeof(game));
    game.kind  = GAME_NONE;
    game_dirty = true;
}

static void game_tick(void) {
    if (game.status != GAME_STATUS_RUNNING) {
        return;
    }
    uint32_t now = timer_read32();
    if (game.kind == GAME_SNAKE) {
        game_snake_tick(now);
    } else if (game.kind == GAME_TETRIS) {
        uint16_t interval = 650 - (game.level - 1) * 50;
        if (interval < 120) {
            interval = 120;
        }
        if (timer_elapsed32(game.last_tick) >= interval) {
            game.last_tick = now;
            game_tetris_move(0, 1);
        }
    }
}

static bool game_apply_action(enum game_action action) {
    if (game.kind == GAME_NONE) {
        switch (action) {
            case GAME_ACTION_CONFIRM:
                game_start(game.menu_selection == 0 ? GAME_SNAKE : GAME_TETRIS);
                break;
            case GAME_ACTION_LEFT:
            case GAME_ACTION_ROTATE:
                game.menu_selection = (game.menu_selection + 1) % 2;
                game_dirty          = true;
                break;
            case GAME_ACTION_RIGHT:
            case GAME_ACTION_DOWN:
                game.menu_selection = (game.menu_selection + 1) % 2;
                game_dirty          = true;
                break;
            case GAME_ACTION_EXIT:
                game_stop();
                break;
            default:
                break;
        }
        return game.kind != GAME_NONE;
    }

    switch (action) {
        case GAME_ACTION_CONFIRM:
            break;
        case GAME_ACTION_PAUSE:
            if (game.kind != GAME_NONE && game.status != GAME_STATUS_OVER) {
                game.status    = game.status == GAME_STATUS_RUNNING ? GAME_STATUS_PAUSED : GAME_STATUS_RUNNING;
                game.last_tick = timer_read32();
                game_dirty     = true;
            }
            break;
        case GAME_ACTION_RESTART:
            if (game.kind != GAME_NONE) {
                game_start(game.kind);
            }
            break;
        case GAME_ACTION_EXIT:
            game_stop();
            break;
        case GAME_ACTION_LEFT:
            if (game.kind == GAME_SNAKE) {
                game_snake_turn(3);
            } else if (game.kind == GAME_TETRIS) {
                game_tetris_move(-1, 0);
            }
            break;
        case GAME_ACTION_RIGHT:
            if (game.kind == GAME_SNAKE) {
                game_snake_turn(1);
            } else if (game.kind == GAME_TETRIS) {
                game_tetris_move(1, 0);
            }
            break;
        case GAME_ACTION_DOWN:
            if (game.kind == GAME_SNAKE) {
                game_snake_turn(2);
            } else if (game.kind == GAME_TETRIS) {
                game_tetris_move(0, 1);
                game.last_tick = timer_read32();
            }
            break;
        case GAME_ACTION_ROTATE:
            if (game.kind == GAME_SNAKE) {
                game_snake_turn(0);
            } else if (game.kind == GAME_TETRIS) {
                game_tetris_rotate();
            }
            break;
        case GAME_ACTION_DROP:
            if (game.kind == GAME_TETRIS) {
                game_tetris_hard_drop();
            }
            break;
    }
    return game.kind != GAME_NONE;
}

bool game_handle_action(enum game_action action) {
    if (game_on_right()) {
        return game_apply_action(action);
    }
    if (game_action_count < ARRAY_SIZE(game_action_queue)) {
        uint8_t tail                   = (game_action_head + game_action_count) % ARRAY_SIZE(game_action_queue);
        game_action_queue[tail].action = (uint8_t)action + 1;
        game_action_queue[tail].seq    = ++game_request_seq;
        game_action_count++;
    }
    return true;
}

static void game_set_cell(uint8_t *cells, uint16_t cell) {
    cells[cell >> 3] |= (uint8_t)1 << (cell & 7);
}

static bool game_get_cell(const uint8_t *cells, uint16_t cell) {
    return cells[cell >> 3] & ((uint8_t)1 << (cell & 7));
}

static void game_fill_packet(game_sync_t *packet) {
    memset(packet, 0, sizeof(*packet));
    packet->magic          = GAME_SYNC_MAGIC;
    packet->version        = GAME_SYNC_VERSION;
    packet->game           = game.kind;
    packet->status         = game.status;
    packet->menu_selection = game.menu_selection;
    packet->score          = game.score;

    if (game.kind == GAME_TETRIS) {
        packet->level      = game.level;
        packet->lines      = game.lines;
        packet->next_kind  = game.next_kind;
        packet->piece_kind = game.piece_kind;
        packet->rotation   = game.rotation;
        packet->piece_x    = game.piece_x;
        packet->piece_y    = game.piece_y;

        for (uint8_t row = 0; row < GAME_TETRIS_HEIGHT; row++) {
            for (uint8_t col = 0; col < GAME_TETRIS_WIDTH; col++) {
                if (game.board[row] & ((uint16_t)1 << col)) {
                    game_set_cell(packet->cells, row * GAME_TETRIS_WIDTH + col);
                }
            }
        }
        uint16_t mask = game_tetromino_mask(game.piece_kind, game.rotation);
        for (uint8_t row = 0; row < 4; row++) {
            for (uint8_t col = 0; col < 4; col++) {
                if (!game_mask_cell(mask, row, col)) {
                    continue;
                }
                int8_t x = game.piece_x + col;
                int8_t y = game.piece_y + row;
                if (x >= 0 && x < GAME_TETRIS_WIDTH && y >= 0 && y < GAME_TETRIS_HEIGHT) {
                    game_set_cell(packet->cells, y * GAME_TETRIS_WIDTH + x);
                }
            }
        }
    } else if (game.kind == GAME_SNAKE) {
        packet->snake_length = game.snake_length;
        packet->direction    = game.direction;
        packet->food_x       = game_snake_x(game.food);
        packet->food_y       = game_snake_y(game.food);
        packet->head_x       = game_snake_x(game.snake_body[0]);
        packet->head_y       = game_snake_y(game.snake_body[0]);
        for (uint16_t i = 0; i < game.snake_length; i++) {
            game_set_cell(packet->cells, game.snake_body[i]);
        }
    }
}

static bool game_valid_packet(const game_sync_t *packet) {
    return packet->magic == GAME_SYNC_MAGIC && packet->version == GAME_SYNC_VERSION;
}

#ifdef SPLIT_KEYBOARD
/*
 * The game engine lives on the physical right half, independent of which side
 * is currently USB master.
 *
 * - Right is master: it runs the engine and pushes state to the left slave.
 * - Right is slave: the left master sends key actions and polls the right;
 *   the right callback advances the engine and returns the new state.
 */
static void game_rpc_slave_handler(uint8_t in_buflen, const void *in_data, uint8_t out_buflen, void *out_data) {
    if (in_data == NULL || in_buflen < sizeof(game_sync_t)) {
        return;
    }
    const game_sync_t *request = (const game_sync_t *)in_data;
    if (!game_valid_packet(request)) {
        return;
    }

    if (game_on_right()) {
        if (!request->game_layer_active) {
            if (game.kind != GAME_NONE) {
                game_stop();
            }
        } else {
            if (request->request_action && request->request_seq != game_last_received_seq) {
                game_last_received_seq = request->request_seq;
                game_apply_action((enum game_action)(request->request_action - 1));
            }
            game_tick();
        }

        if (out_data == NULL || out_buflen < sizeof(game_sync_t)) {
            return;
        }
        game_fill_packet((game_sync_t *)out_data);
        memcpy(&game_view, out_data, sizeof(game_view));
    } else {
        memcpy(&game_view, request, sizeof(game_view));
    }
}

static void game_sync_from_right_master(bool game_layer_active) {
    if (!game_dirty && !game_last_sent_active) {
        return;
    }
    if (timer_elapsed32(game_last_exchange) < GAME_RPC_INTERVAL_MS) {
        return;
    }
    game_view.game_layer_active = game_layer_active;
    if (transaction_rpc_send(SOFLE_GAME_SYNC, sizeof(game_view), &game_view)) {
        game_dirty            = false;
        game_last_exchange    = timer_read32();
        game_last_sent_active = game_view.game != GAME_NONE;
    }
}

static void game_poll_right_slave(bool game_layer_active) {
    if (!game_layer_active && game_view.game == GAME_NONE && !game_action_count) {
        return;
    }
    if (timer_elapsed32(game_last_exchange) < GAME_RPC_INTERVAL_MS) {
        return;
    }

    game_sync_t request;
    memset(&request, 0, sizeof(request));
    request.magic             = GAME_SYNC_MAGIC;
    request.version           = GAME_SYNC_VERSION;
    request.game_layer_active = game_layer_active;
    request.request_action    = game_action_count ? game_action_queue[game_action_head].action : 0;
    request.request_seq       = game_action_count ? game_action_queue[game_action_head].seq : 0;

    game_sync_t response;
    memset(&response, 0, sizeof(response));
    if (transaction_rpc_exec(SOFLE_GAME_SYNC, sizeof(request), &request, sizeof(response), &response) && game_valid_packet(&response)) {
        memcpy(&game_view, &response, sizeof(game_view));
        if (request.request_action) {
            game_action_head = (game_action_head + 1) % ARRAY_SIZE(game_action_queue);
            game_action_count--;
        }
        game_dirty         = false;
        game_last_exchange = timer_read32();
    }
}
#endif

void game_init(void) {
    memset(&game, 0, sizeof(game));
    memset(&game_view, 0, sizeof(game_view));
    game_view.magic   = GAME_SYNC_MAGIC;
    game_view.version = GAME_SYNC_VERSION;
#ifdef SPLIT_KEYBOARD
    transaction_register_rpc(SOFLE_GAME_SYNC, game_rpc_slave_handler);
#endif
}

void game_housekeeping(bool game_layer_active) {
    if (game_on_right()) {
        if (!game_layer_active && game.kind != GAME_NONE) {
            game_stop();
        }
        if (game_layer_active) {
            game_tick();
        }
        game_fill_packet(&game_view);
#ifdef SPLIT_KEYBOARD
        if (is_keyboard_master()) {
            game_sync_from_right_master(game_layer_active);
        }
#endif
        return;
    }

#ifdef SPLIT_KEYBOARD
    if (is_keyboard_master()) {
        game_poll_right_slave(game_layer_active);
    }
#else
    (void)game_layer_active;
#endif
}

#ifdef OLED_ENABLE
static uint8_t game_canvas[GAME_CANVAS_SIZE];

static void game_canvas_clear(void) {
    memset(game_canvas, 0, sizeof(game_canvas));
}

static void game_canvas_pixel(uint8_t x, uint8_t y, bool on) {
    if (x >= GAME_CANVAS_WIDTH || y >= GAME_CANVAS_HEIGHT) {
        return;
    }
    uint16_t index = x + (y / 8) * GAME_CANVAS_WIDTH;
    if (on) {
        game_canvas[index] |= (uint8_t)1 << (y & 7);
    } else {
        game_canvas[index] &= ~((uint8_t)1 << (y & 7));
    }
}

static bool game_canvas_get(uint8_t x, uint8_t y) {
    return game_canvas[x + (y / 8) * GAME_CANVAS_WIDTH] & ((uint8_t)1 << (y & 7));
}

static void game_canvas_flush(void) {
    oled_clear();
    for (uint8_t y = 0; y < GAME_CANVAS_HEIGHT; y++) {
        for (uint8_t x = 0; x < GAME_CANVAS_WIDTH; x++) {
            if (game_canvas_get(x, y)) {
                oled_write_pixel(x, y, true);
            }
        }
    }
}

static void game_canvas_rect(uint8_t x, uint8_t y, uint8_t width, uint8_t height, bool fill) {
    if (!fill) {
        for (uint8_t i = 0; i < width; i++) {
            game_canvas_pixel(x + i, y, true);
            game_canvas_pixel(x + i, y + height - 1, true);
        }
        for (uint8_t i = 0; i < height; i++) {
            game_canvas_pixel(x, y + i, true);
            game_canvas_pixel(x + width - 1, y + i, true);
        }
        return;
    }
    for (uint8_t yy = 0; yy < height; yy++) {
        for (uint8_t xx = 0; xx < width; xx++) {
            game_canvas_pixel(x + xx, y + yy, true);
        }
    }
}

static void game_canvas_clear_rect(uint8_t x, uint8_t y, uint8_t width, uint8_t height) {
    for (uint8_t yy = 0; yy < height; yy++) {
        for (uint8_t xx = 0; xx < width; xx++) {
            game_canvas_pixel(x + xx, y + yy, false);
        }
    }
}

static const uint8_t game_font[36][7] = {
    {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}, // A
    {0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E}, // B
    {0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E}, // C
    {0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C}, // D
    {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F}, // E
    {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10}, // F
    {0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F}, // G
    {0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}, // H
    {0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E}, // I
    {0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C}, // J
    {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11}, // K
    {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F}, // L
    {0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11}, // M
    {0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11}, // N
    {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}, // O
    {0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10}, // P
    {0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D}, // Q
    {0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11}, // R
    {0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E}, // S
    {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}, // T
    {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}, // U
    {0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04}, // V
    {0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A}, // W
    {0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11}, // X
    {0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04}, // Y
    {0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F}, // Z
    {0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E}, // 0
    {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E}, // 1
    {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F}, // 2
    {0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E}, // 3
    {0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02}, // 4
    {0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E}, // 5
    {0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E}, // 6
    {0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}, // 7
    {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E}, // 8
    {0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C}, // 9
};

static const uint8_t *game_glyph(char c) {
    if (c >= 'A' && c <= 'Z') {
        return game_font[c - 'A'];
    }
    if (c >= '0' && c <= '9') {
        return game_font[26 + c - '0'];
    }
    return NULL;
}

static void game_canvas_text_draw(uint8_t x, uint8_t y, const char *text, uint8_t scale, bool on) {
    while (*text) {
        const uint8_t *glyph = game_glyph(*text++);
        if (glyph) {
            for (uint8_t row = 0; row < 7; row++) {
                for (uint8_t col = 0; col < 5; col++) {
                    if (!(glyph[row] & (1 << (4 - col)))) {
                        continue;
                    }
                    for (uint8_t sy = 0; sy < scale; sy++) {
                        for (uint8_t sx = 0; sx < scale; sx++) {
                            game_canvas_pixel(x + col * scale + sx, y + row * scale + sy, on);
                        }
                    }
                }
            }
        }
        x += 6 * scale;
    }
}

static void game_canvas_text(uint8_t x, uint8_t y, const char *text, uint8_t scale) {
    game_canvas_text_draw(x, y, text, scale, true);
}

static void game_canvas_text_selected(uint8_t y, const char *text) {
    game_canvas_rect(3, y - 2, 58, 12, true);
    game_canvas_text_draw(6, y, text, 1, false);
}

static void game_canvas_number(uint8_t x, uint8_t y, uint16_t value, uint8_t scale) {
    char    buf[6];
    uint8_t pos = sizeof(buf) - 1;
    buf[pos]    = '\0';
    do {
        buf[--pos] = '0' + value % 10;
        value /= 10;
    } while (value);
    game_canvas_text(x, y, &buf[pos], scale);
}

static void game_canvas_block(uint8_t x, uint8_t y, uint8_t width, uint8_t height, uint8_t gap) {
    game_canvas_rect(x, y, width - gap, height - gap, true);
}

static void game_canvas_next_piece(uint8_t kind, uint8_t x0, uint8_t y0, uint8_t cell) {
    uint16_t mask    = game_tetromino_mask(kind, 0);
    uint8_t  min_row = 4, max_row = 0, min_col = 4, max_col = 0;
    for (uint8_t row = 0; row < 4; row++) {
        for (uint8_t col = 0; col < 4; col++) {
            if (!game_mask_cell(mask, row, col)) {
                continue;
            }
            if (row < min_row) min_row = row;
            if (row > max_row) max_row = row;
            if (col < min_col) min_col = col;
            if (col > max_col) max_col = col;
        }
    }
    uint8_t width  = (max_col - min_col + 1) * cell;
    uint8_t height = (max_row - min_row + 1) * cell;
    uint8_t x      = x0 + (56 - width) / 2;
    uint8_t y      = y0 + (42 - height) / 2;
    for (uint8_t row = min_row; row <= max_row; row++) {
        for (uint8_t col = min_col; col <= max_col; col++) {
            if (game_mask_cell(mask, row, col)) {
                game_canvas_block(x + (col - min_col) * cell, y + (row - min_row) * cell, cell, cell, 1);
            }
        }
    }
}

static void game_canvas_border(void) {
    game_canvas_rect(0, 0, GAME_CANVAS_WIDTH, GAME_CANVAS_HEIGHT, false);
}

static void game_render_menu(void) {
    game_canvas_clear();
    game_canvas_border();
    if (is_keyboard_left()) {
        game_canvas_text(4, 8, "GAME", 2);
        game_canvas_rect(4, 30, 56, 1, true);
        if (game_view.menu_selection == 0) {
            game_canvas_text_selected(46, "SNAKE");
            game_canvas_text(6, 66, "TETRIS", 1);
        } else {
            game_canvas_text(6, 46, "SNAKE", 1);
            game_canvas_text_selected(66, "TETRIS");
        }
        game_canvas_text(6, 104, "ENTER", 1);
    }
    game_canvas_flush();
}

static void game_render_tetris_sidebar(void) {
    game_canvas_clear();
    game_canvas_border();
    game_canvas_text(4, 4, "NEXT", 1);
    if (game_view.next_kind < 7) {
        game_canvas_next_piece(game_view.next_kind, 4, 15, 8);
    }

    game_canvas_text(4, 62, "SCORE", 1);
    game_canvas_number(4, 72, game_view.score, 2);
    game_canvas_text(4, 92, "LEVEL", 1);
    game_canvas_number(50, 92, game_view.level, 1);
    game_canvas_text(4, 104, "LINES", 1);
    game_canvas_number(50, 104, game_view.lines, 1);

    if (game_view.status == GAME_STATUS_PAUSED) {
        game_canvas_text(4, 118, "PAUSED", 1);
    } else if (game_view.status == GAME_STATUS_OVER) {
        game_canvas_text(4, 118, "OVER", 1);
    }
    game_canvas_flush();
}

static void game_render_tetris_board(void) {
    game_canvas_clear();
    game_canvas_border();
    const uint8_t cell     = GAME_TETRIS_CELL_SIZE;
    const uint8_t origin_x = 2;
    const uint8_t origin_y = 4;
    for (uint8_t row = 0; row < GAME_TETRIS_HEIGHT; row++) {
        for (uint8_t col = 0; col < GAME_TETRIS_WIDTH; col++) {
            if (game_get_cell(game_view.cells, row * GAME_TETRIS_WIDTH + col)) {
                game_canvas_block(origin_x + col * cell, origin_y + row * cell, cell, cell, 1);
            }
        }
    }
    game_canvas_flush();
}

static void game_render_snake_info(void) {
    game_canvas_clear();
    game_canvas_border();
    game_canvas_text(2, 8, "SNAKE", 2);
    game_canvas_text(4, 38, "SCORE", 1);
    game_canvas_number(4, 48, game_view.score, 2);
    game_canvas_text(4, 76, "LENGTH", 1);
    game_canvas_number(4, 86, game_view.snake_length, 1);
    game_canvas_text(4, 108, "STATUS", 1);
    if (game_view.status == GAME_STATUS_PAUSED) {
        game_canvas_text(4, 118, "PAUSED", 1);
    } else if (game_view.status == GAME_STATUS_OVER) {
        game_canvas_text(4, 118, "GAME OVER", 1);
    } else {
        game_canvas_text(4, 118, "RUNNING", 1);
    }
    game_canvas_flush();
}

static void game_render_snake(void) {
    game_canvas_clear();
    game_canvas_border();
    const uint8_t top  = 2;
    const uint8_t cell = 4;
    for (uint8_t row = 0; row < GAME_SNAKE_HEIGHT; row++) {
        for (uint8_t col = 0; col < GAME_SNAKE_WIDTH; col++) {
            if (game_get_cell(game_view.cells, row * GAME_SNAKE_WIDTH + col)) {
                game_canvas_block(col * cell, top + row * cell, cell, cell, 0);
            }
        }
    }

    uint8_t food_x = game_view.food_x * cell;
    uint8_t food_y = top + game_view.food_y * cell;
    game_canvas_rect(food_x + 1, food_y + 1, 2, 2, true);

    uint8_t head_x = game_view.head_x * cell;
    uint8_t head_y = top + game_view.head_y * cell;
    game_canvas_clear_rect(head_x + 1, head_y + 1, 2, 2);

    game_canvas_flush();
}
#endif

bool game_oled_task(bool game_layer_active) {
#ifdef OLED_ENABLE
    static game_sync_t drawn_view;
    static bool        have_drawn_view;

    if (!game_layer_active) {
        have_drawn_view = false;
        return false;
    }
    if (have_drawn_view && memcmp(&drawn_view, &game_view, sizeof(game_view)) == 0) {
        return true;
    }
    if (game_view.game == GAME_NONE || !game_valid_packet(&game_view)) {
        game_render_menu();
        memcpy(&drawn_view, &game_view, sizeof(drawn_view));
        have_drawn_view = true;
        return true;
    }
    if (game_view.game == GAME_TETRIS) {
        if (is_keyboard_left()) {
            game_render_tetris_sidebar();
        } else {
            game_render_tetris_board();
        }
    } else {
        if (is_keyboard_left()) {
            game_render_snake_info();
        } else {
            game_render_snake();
        }
    }
    memcpy(&drawn_view, &game_view, sizeof(drawn_view));
    have_drawn_view = true;
    return true;
#else
    (void)game_layer_active;
    return false;
#endif
}
