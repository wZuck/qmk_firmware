/* harness.c -- run QMK's REAL rgb_matrix effect code as a native macOS
 * program and dump the 58 sofle_pico WS2812 values as JSON.
 *
 *     ./harness --frames 120 --dt-ms 68 --out led_frames.json
 *
 * Design rules (see README.md for the full story):
 *   * The effect maths is NOT re-implemented.  The eight effect headers, the
 *     six effect runners and `hsv_to_rgb()` are the repository's own files,
 *     compiled by this build.
 *   * Everything that the keyboard firmware would supply from
 *     `quantum/rgb_matrix/rgb_matrix.c` (globals, set_color, limits, key
 *     events, tick bookkeeping, the task state machine) is copied from that
 *     file; the sections below quote the line numbers they came from.
 *   * Only split/chibios/EEPROM branches are dropped.
 */

#include <stdio.h>
#include <sys/stat.h>

#include "qmk_host.h"

/* ---------------------------------------------------------------------------
 * Real data + real effect sources
 * ------------------------------------------------------------------------ */

/* g_led_config for sofle_pico, extracted from the compiled firmware artifact
 * by extract_led_config.py -- never hand-copied. */
#include "led_config_gen.h"

/* quantum/rgb_matrix/animations/runners/rgb_matrix_runners.inc
 * (== the six effect_runner_*.h includes) */
#include "rgb_matrix_runners.inc"

/* The eight requested effects, included exactly the way rgb_matrix.c does it
 * (rgb_matrix.c:44-62): a no-op RGB_MATRIX_EFFECT() plus
 * RGB_MATRIX_CUSTOM_EFFECT_IMPLS makes each header emit its implementation.
 * They are included one by one (rather than through rgb_matrix_effects.inc)
 * so that only these eight are compiled, while the enum above still uses the
 * complete effects.inc and therefore keeps the firmware's mode numbers. */
#define RGB_MATRIX_EFFECT(name)
#define RGB_MATRIX_CUSTOM_EFFECT_IMPLS

#include "cycle_out_in_anim.h"
#include "hue_wave_anim.h"
#include "rainbow_beacon_anim.h"
#include "digital_rain_anim.h"
#include "jellybean_raindrops_anim.h"
/* pixel_flow_anim.h contains a GCC nested function, which Apple clang rejects.
 * `prepare_effects.py` hoists it to file scope (pure move, verified) into
 * generated/pixel_flow_anim.h.  See README.md. */
#include "generated/pixel_flow_anim.h"
#include "solid_reactive_nexus.h"
#include "typing_heatmap_anim.h"

#undef RGB_MATRIX_CUSTOM_EFFECT_IMPLS
#undef RGB_MATRIX_EFFECT

/* ---------------------------------------------------------------------------
 * Globals -- rgb_matrix.c:31-98
 * ------------------------------------------------------------------------ */

/* rgb_matrix.c:31-35 */
#ifndef RGB_MATRIX_CENTER
const led_point_t k_rgb_matrix_center = {112, 32};
#else
const led_point_t k_rgb_matrix_center = RGB_MATRIX_CENTER;
#endif

/* rgb_matrix.c:66-73 */
rgb_config_t rgb_matrix_config;
uint32_t     g_rgb_timer;
#ifdef RGB_MATRIX_FRAMEBUFFER_EFFECTS
uint8_t g_rgb_frame_buffer[MATRIX_ROWS][MATRIX_COLS] = {{0}};
#endif
#ifdef RGB_MATRIX_KEYREACTIVE_ENABLED
last_hit_t g_last_hit_tracker;
#endif

/* rgb_matrix.c:86 */
static effect_params_t rgb_effect_params = {0, LED_FLAG_ALL, false};

/* rgb_matrix.c:83-84 -- last effect/enable, used to compute `params->init` */
static uint8_t rgb_last_enable = UINT8_MAX;
static uint8_t rgb_last_effect = UINT8_MAX;

/* rgb_matrix.c:85 -- effect picked in STARTING and rendered until FLUSHING */
static uint8_t rgb_current_effect = 0;

/* Virtual clock / RNG settings owned by main(); declared here because the
 * frame driver below needs them. */
static uint32_t g_frame_dt_ms = 68;
static uint32_t g_seed        = 555;

/* rgb_matrix.c:90-93 -- double buffers */
static uint32_t rgb_timer_buffer;
#ifdef RGB_MATRIX_KEYREACTIVE_ENABLED
static last_hit_t last_hit_buffer;
#endif

/* ---------------------------------------------------------------------------
 * LED driver stand-in.
 *
 * `rgb_matrix_driver.set_color` / `.set_color_all` for RGB_MATRIX_DRIVER =
 * ws2812 are `platforms/chibios/drivers/vendor/RP/RP2040/ws2812_vendor.c`
 * :271-284: one rgb_t per LED, set_color writes a single entry, set_color_all
 * loops over all of them.  That is all the harness needs, so the driver is
 * replaced by the same two functions over a plain array.  (No split branch ->
 * WS2812_LED_COUNT == RGB_MATRIX_LED_COUNT == 58.)
 *
 * Note this buffer is deliberately NOT cleared between frames; on the real
 * keyboard it also survives from one frame to the next (that is why
 * jellybean_raindrops can light one LED per frame).
 * ------------------------------------------------------------------------ */
static rgb_t led_buffer[RGB_MATRIX_LED_COUNT];

void rgb_matrix_set_color(int index, uint8_t red, uint8_t green, uint8_t blue) {
    /* rgb_matrix.c:179-186 minus rgb_matrix_led_index(): that helper only
     * decides whether this half of a split keyboard owns `index`, and the
     * harness renders both halves. The ws2812 driver itself does no bounds
     * check either; the guard here is a harness-only crash net. */
    if (index < 0 || index >= RGB_MATRIX_LED_COUNT) {
        fprintf(stderr, "harness: rgb_matrix_set_color(%d) out of range\n", index);
        abort();
    }
    led_buffer[index].r = red;
    led_buffer[index].g = green;
    led_buffer[index].b = blue;
}

void rgb_matrix_set_color_all(uint8_t red, uint8_t green, uint8_t blue) {
    /* rgb_matrix.c:188-195, non-split path: rgb_matrix_driver.set_color_all() */
    for (int i = 0; i < RGB_MATRIX_LED_COUNT; i++) {
        rgb_matrix_set_color(i, red, green, blue);
    }
}

/* ---------------------------------------------------------------------------
 * Framework -- rgb_matrix.c (line numbers refer to that file)
 * ------------------------------------------------------------------------ */

/* rgb_matrix.c:37-39.
 *
 * The firmware itself is compiled with -DUSE_CIE1931_CURVE (see
 * .build/obj_sofle_pico_default/cflags.txt), i.e. quantum/color.c's
 * `hsv_to_rgb()` runs the value channel through the CIE 1931 lightness curve.
 * The harness keeps that as the default so the numbers match the LEDs;
 * `--no-cie` selects the other real function instead (`hsv_to_rgb_nocie()`,
 * also from quantum/color.c). */
static bool g_use_cie1931 = true;

rgb_t rgb_matrix_hsv_to_rgb(hsv_t hsv) {
    return g_use_cie1931 ? hsv_to_rgb(hsv) : hsv_to_rgb_nocie(hsv);
}

/* rgb_matrix.c:141-153, including the keyboard hook from default_keyboard.c
 * (`rgb_matrix_map_row_column_to_led_kb` returns 0 there too). */
__attribute__((weak)) uint8_t rgb_matrix_map_row_column_to_led_kb(uint8_t row, uint8_t column, uint8_t *led_i) {
    (void)row;
    (void)column;
    (void)led_i;
    return 0;
}

uint8_t rgb_matrix_map_row_column_to_led(uint8_t row, uint8_t column, uint8_t *led_i) {
    uint8_t led_count = rgb_matrix_map_row_column_to_led_kb(row, column, led_i);
    uint8_t led_index = g_led_config.matrix_co[row][column];
    if (led_index != NO_LED) {
        led_i[led_count] = led_index;
        led_count++;
    }
    return led_count;
}

/* rgb_matrix.c:197-245.
 *
 * Two changes, both because the harness never defines RGB_MATRIX_SPLIT:
 *   - the `#ifndef RGB_MATRIX_SPLIT / if (!is_keyboard_master()) return;`
 *     master gate is dropped.  For this split keyboard the firmware defines
 *     RGB_MATRIX_SPLIT, so that gate is not compiled into the firmware
 *     either -- dropping it here is what keeps us faithful.
 *   - (nothing else; the buffer bookkeeping and the typing-heatmap call are
 *     verbatim, including the `mode == RGB_MATRIX_TYPING_HEATMAP` condition.)
 */
void rgb_matrix_handle_key_event(uint8_t row, uint8_t col, bool pressed) {
#ifdef RGB_MATRIX_KEYREACTIVE_ENABLED
    uint8_t led[LED_HITS_TO_REMEMBER];
    uint8_t led_count = 0;

#    if defined(RGB_MATRIX_KEYRELEASES)
    if (!pressed)
#    elif defined(RGB_MATRIX_KEYPRESSES)
    if (pressed)
#    endif // defined(RGB_MATRIX_KEYRELEASES)
    {
        led_count = rgb_matrix_map_row_column_to_led(row, col, led);
    }

    if (last_hit_buffer.count + led_count > LED_HITS_TO_REMEMBER) {
        memmove(&last_hit_buffer.x[0], &last_hit_buffer.x[led_count], LED_HITS_TO_REMEMBER - led_count);
        memmove(&last_hit_buffer.y[0], &last_hit_buffer.y[led_count], LED_HITS_TO_REMEMBER - led_count);
        memmove(&last_hit_buffer.tick[0], &last_hit_buffer.tick[led_count], (LED_HITS_TO_REMEMBER - led_count) * 2); // 16 bit
        memmove(&last_hit_buffer.index[0], &last_hit_buffer.index[led_count], LED_HITS_TO_REMEMBER - led_count);
        last_hit_buffer.count = LED_HITS_TO_REMEMBER - led_count;
    }

    for (uint8_t i = 0; i < led_count; i++) {
        uint8_t index                = last_hit_buffer.count;
        last_hit_buffer.x[index]     = g_led_config.point[led[i]].x;
        last_hit_buffer.y[index]     = g_led_config.point[led[i]].y;
        last_hit_buffer.index[index] = led[i];
        last_hit_buffer.tick[index]  = 0;
        last_hit_buffer.count++;
    }
#endif // RGB_MATRIX_KEYREACTIVE_ENABLED

#if defined(RGB_MATRIX_FRAMEBUFFER_EFFECTS) && defined(ENABLE_RGB_MATRIX_TYPING_HEATMAP)
#    if defined(RGB_MATRIX_KEYRELEASES)
    if (!pressed)
#    else
    if (pressed)
#    endif // defined(RGB_MATRIX_KEYRELEASES)
    {
        if (rgb_matrix_config.mode == RGB_MATRIX_TYPING_HEATMAP) {
            process_rgb_matrix_typing_heatmap(row, col);
        }
    }
#endif
}

/* rgb_matrix.c:455-481, reduced to the branch the firmware actually takes.
 *
 * The firmware leaves RGB_MATRIX_LED_PROCESS_LIMIT undefined, so
 * rgb_matrix.h:89-91 defaults it to (58+4)/5 == 12 and this function returns
 * five 12-LED windows.  The harness pins the limit to 58 (see qmk_host.h) and
 * therefore takes rgb_matrix.c's `#else` branch, which (with no
 * RGB_MATRIX_SPLIT) is exactly:
 */
struct rgb_matrix_limits_t rgb_matrix_get_limits(uint8_t iter) {
    struct rgb_matrix_limits_t limits = {0};
    (void)iter;
    limits.led_min_index = 0;
    limits.led_max_index = RGB_MATRIX_LED_COUNT;
    return limits;
}

/* rgb_matrix.c:280-297.
 *
 * The firmware reads real elapsed milliseconds here.  The harness owns a
 * virtual millisecond clock (`rgb_timer_buffer`) and hands this function the
 * frame budget `dt_ms`; the tick bookkeeping (including the
 * `UINT16_MAX - deltaTime < tick` drop and the `count--`) is verbatim. */
static void rgb_task_timers(uint32_t deltaTime) {
    rgb_timer_buffer += deltaTime;

    // Update double buffer last hit timers
#ifdef RGB_MATRIX_KEYREACTIVE_ENABLED
    uint8_t count = last_hit_buffer.count;
    for (uint8_t i = 0; i < count; ++i) {
        if (UINT16_MAX - deltaTime < last_hit_buffer.tick[i]) {
            last_hit_buffer.count--;
            continue;
        }
        last_hit_buffer.tick[i] += deltaTime;
    }
#endif // RGB_MATRIX_KEYREACTIVE_ENABLED
}

/* rgb_matrix.c:305-328, minus the suspend/timeout/EEPROM bits. */
static void rgb_task_start(void) {
    // reset iter
    rgb_effect_params.iter = 0;

    // update double buffers
    g_rgb_timer = rgb_timer_buffer;
#ifdef RGB_MATRIX_KEYREACTIVE_ENABLED
    g_last_hit_tracker = last_hit_buffer;
#endif

    // Set effect to be rendered
    rgb_current_effect = rgb_matrix_config.enable ? rgb_matrix_config.mode : 0;
}

/* rgb_matrix.c:330-397, with the switch over the eight modelled effects.
 * Returns true when the matrix is complete and the firmware would move to
 * FLUSHING. */
typedef bool (*effect_fn_t)(effect_params_t *params);

typedef struct {
    const char *name;
    uint8_t     mode;
    effect_fn_t fn;
} effect_desc_t;

// clang-format off
static const effect_desc_t k_effects[] = {
    {"cycle_out_in",              RGB_MATRIX_CYCLE_OUT_IN,              CYCLE_OUT_IN},
    {"hue_wave",                  RGB_MATRIX_HUE_WAVE,                  HUE_WAVE},
    {"rainbow_beacon",            RGB_MATRIX_RAINBOW_BEACON,            RAINBOW_BEACON},
    {"digital_rain",              RGB_MATRIX_DIGITAL_RAIN,              DIGITAL_RAIN},
    {"jellybean_raindrops",       RGB_MATRIX_JELLYBEAN_RAINDROPS,       JELLYBEAN_RAINDROPS},
    {"pixel_flow",                RGB_MATRIX_PIXEL_FLOW,                PIXEL_FLOW},
    {"solid_reactive_multinexus", RGB_MATRIX_SOLID_REACTIVE_MULTINEXUS, SOLID_REACTIVE_MULTINEXUS},
    {"typing_heatmap",            RGB_MATRIX_TYPING_HEATMAP,            TYPING_HEATMAP},
};
// clang-format on

#define ARRAY_SIZE_OF(a) (sizeof(a) / sizeof((a)[0]))

static bool rgb_task_render(uint8_t effect) {
    bool rendering         = false;
    rgb_effect_params.init = (effect != rgb_last_effect) || (rgb_matrix_config.enable != rgb_last_enable);
    if (rgb_effect_params.flags != rgb_matrix_config.flags) {
        rgb_effect_params.flags = rgb_matrix_config.flags;
        rgb_matrix_set_color_all(0, 0, 0);
    }

    for (size_t e = 0; e < ARRAY_SIZE_OF(k_effects); e++) {
        if (k_effects[e].mode == effect) {
            rendering = k_effects[e].fn(&rgb_effect_params);
            break;
        }
    }

    rgb_effect_params.iter++;

    // `!rendering` means "all LEDs done" -> FLUSHING
    return !rendering;
}

/* rgb_matrix.c:399-409; rgb_matrix_update_pwm_buffers() is where the caller
 * snapshots led_buffer. */
static void rgb_task_flush(uint8_t effect) {
    rgb_last_effect = effect;
    rgb_last_enable = rgb_matrix_config.enable;
}

/* One output frame == one full rgb_matrix_task() cycle: timers -> STARTING ->
 * RENDERING (until the matrix is complete) -> FLUSHING -> SYNCING.
 *
 * rgb_task_timers() runs once per frame, advancing the virtual clock and the
 * hit ticks by `dt_ms`; the firmware would run it on every 1 ms task call, so
 * the total tick advance over one frame is the same.  rgb_task_sync()'s
 * 16 ms flush limit is not modelled: frames are assumed to be at least that
 * long (the default 68 ms is), otherwise the firmware would coalesce frames.
 */
static void rgb_task_frame(void) {
    rgb_task_timers(g_frame_dt_ms);

    rgb_task_start();

    bool finished = false;
    for (int guard = 0; guard < 64 && !finished; guard++) {
        finished = rgb_task_render(rgb_current_effect);
    }

    rgb_task_flush(rgb_current_effect);
}

/* ---------------------------------------------------------------------------
 * Platform timing stand-ins (virtual clock, in ms)
 * ------------------------------------------------------------------------ */
uint16_t timer_read(void) {
    return (uint16_t)rgb_timer_buffer;
}
uint16_t timer_elapsed(uint16_t last) {
    return (uint16_t)(timer_read() - last);
}
uint32_t get_millisecond_timer(void) {
    return rgb_timer_buffer;
}

/* ---------------------------------------------------------------------------
 * Typing script -- one deterministic sequence shared by every effect
 * ------------------------------------------------------------------------ */
typedef struct {
    uint8_t row;
    uint8_t col;
} key_pos_t;

/* Home-row dominant, strictly alternating hands, both halves, a few travel
 * keys.  Column order per half: 0 = pinky .. 5 = inner.  Left half home row is
 * matrix row 1, right half home row is matrix row 6 (see g_led_config above).
 * (0,1)/(5,4) etc. also exercise the upper rows. */
static const key_pos_t k_typing_sequence[] = {
    {1, 0}, {6, 3}, // a  / j
    {1, 1}, {6, 4}, // s  / k
    {1, 2}, {6, 2}, // d  / l
    {1, 3}, {6, 1}, // f  / ;
    {0, 2}, {5, 3}, // e  / u
    {2, 3}, {7, 3}, // v  / m
    {1, 4}, {6, 5}, // g  / h  (inner columns)
    {0, 1}, {5, 4}, // w  / i
};

static size_t           typing_cursor;
static const key_pos_t *typing_last;

static void typing_script_reset(void) {
    typing_cursor = 0;
    typing_last   = NULL;
}

/* Presses start on frame 1 and repeat every 3 frames; the release follows on
 * the next frame.  Frame 0 is deliberately left alone because that is the
 * frame on which the effect sees `params->init` and clears its state (both
 * digital_rain and typing_heatmap wipe g_rgb_frame_buffer there).
 *
 * RGB_MATRIX_KEYPRESSES (not _KEYRELEASES) is enabled, so the release call is a
 * no-op inside rgb_matrix_handle_key_event -- exactly as on the real keyboard. */
static void typing_script_step(uint32_t frame) {
    const uint32_t phase = frame + 2; /* shift the script so it starts on frame 1 */
    if (phase % 3 == 0) {
        const key_pos_t *k = &k_typing_sequence[typing_cursor];
        rgb_matrix_handle_key_event(k->row, k->col, true);
        typing_last = k;
        typing_cursor++;
        if (typing_cursor >= ARRAY_SIZE_OF(k_typing_sequence)) typing_cursor = 0;
    } else if (phase % 3 == 1 && typing_last != NULL) {
        rgb_matrix_handle_key_event(typing_last->row, typing_last->col, false);
    }
}

/* ---------------------------------------------------------------------------
 * Effect run + JSON output
 * ------------------------------------------------------------------------ */

static uint8_t g_hue = RGB_MATRIX_DEFAULT_HUE;
static uint8_t g_sat = RGB_MATRIX_DEFAULT_SAT;
static uint8_t g_val = RGB_MATRIX_DEFAULT_VAL;
static uint8_t g_speed = RGB_MATRIX_DEFAULT_SPD;

/* rgb_matrix.c:506-519 + eeconfig_update_rgb_matrix_default():207-114, with
 * the EEPROM read replaced by the compile-time defaults. */
static void harness_state_reset(uint8_t mode, uint32_t seed) {
    rgb_matrix_config.raw    = 0;
    rgb_matrix_config.enable = 1;
    rgb_matrix_config.mode   = mode;
    rgb_matrix_config.hsv    = (hsv_t){g_hue, g_sat, g_val};
    rgb_matrix_config.speed  = g_speed;
    rgb_matrix_config.flags  = LED_FLAG_ALL;

    rgb_timer_buffer = 0;
    g_rgb_timer      = 0;

    memset(g_rgb_frame_buffer, 0, sizeof(g_rgb_frame_buffer));

#ifdef RGB_MATRIX_KEYREACTIVE_ENABLED
    g_last_hit_tracker.count = 0;
    for (uint8_t i = 0; i < LED_HITS_TO_REMEMBER; ++i) {
        g_last_hit_tracker.tick[i] = UINT16_MAX;
    }
    last_hit_buffer.count = 0;
    for (uint8_t i = 0; i < LED_HITS_TO_REMEMBER; ++i) {
        last_hit_buffer.tick[i] = UINT16_MAX;
    }
#endif

    memset(led_buffer, 0, sizeof(led_buffer));

    rgb_effect_params.iter  = 0;
    rgb_effect_params.flags = LED_FLAG_ALL;
    rgb_effect_params.init  = false;
    rgb_last_effect         = UINT8_MAX; /* -> params->init on the first frame */
    rgb_last_enable         = UINT8_MAX;
    rgb_current_effect      = mode;

    /* Deterministic randomness: BOTH generators are re-seeded before every
     * effect so all eight see exactly the same stream. */
    srand(seed);                        /* digital_rain uses rand()/RAND_MAX */
    random16_set_seed((uint16_t)seed);  /* lib8tion random8()/random16() */

    typing_script_reset();
}

/* Runs one effect for `frames` frames; writes frames*58*3 bytes to `out`. */
static void run_effect(const effect_desc_t *e, uint32_t frames, uint8_t *out) {
    harness_state_reset(e->mode, g_seed);
    for (uint32_t f = 0; f < frames; f++) {
        typing_script_step(f);
        rgb_task_frame();
        memcpy(out + (size_t)f * RGB_MATRIX_LED_COUNT * 3, led_buffer, RGB_MATRIX_LED_COUNT * 3);
    }
}

static void write_json(FILE *fp, uint32_t frames, uint32_t dt_ms, uint8_t *const *frames_by_effect) {
    fprintf(fp,
            "{\n"
            "  \"led_count\": %d,\n"
            "  \"frames\": %u,\n"
            "  \"dt_ms\": %u,\n"
            "  \"speed\": %u,\n"
            "  \"hsv\": [%u, %u, %u],\n"
            "  \"max_brightness\": %d,\n"
            "  \"effects\": [\n",
            RGB_MATRIX_LED_COUNT, (unsigned)frames, (unsigned)dt_ms, (unsigned)g_speed, (unsigned)g_hue, (unsigned)g_sat, (unsigned)g_val, RGB_MATRIX_MAXIMUM_BRIGHTNESS);

    for (size_t e = 0; e < ARRAY_SIZE_OF(k_effects); e++) {
        fprintf(fp, "    {\"name\": \"%s\", \"mode\": %u, \"frames\": [", k_effects[e].name, (unsigned)k_effects[e].mode);
        for (uint32_t f = 0; f < frames; f++) {
            const uint8_t *px = frames_by_effect[e] + (size_t)f * RGB_MATRIX_LED_COUNT * 3;
            fputc('[', fp);
            for (int i = 0; i < RGB_MATRIX_LED_COUNT; i++) {
                fprintf(fp, "[%u,%u,%u]", px[i * 3 + 0], px[i * 3 + 1], px[i * 3 + 2]);
                if (i != RGB_MATRIX_LED_COUNT - 1) fputc(',', fp);
            }
            fputc(']', fp);
            if (f != frames - 1) fputc(',', fp);
        }
        fprintf(fp, "]}%s\n", e + 1 == ARRAY_SIZE_OF(k_effects) ? "" : ",");
    }
    fprintf(fp, "  ]\n}\n");
}

static void usage(const char *argv0) {
    fprintf(stderr,
            "usage: %s [--frames N] [--dt-ms N] [--out PATH|-] [--speed N] [--hue N] [--sat N] [--val N]\n"
            "          [--seed N] [--no-cie] [--list-modes]\n"
            "\n"
            "  --frames N   number of frames per effect (default 120)\n"
            "  --dt-ms N    virtual milliseconds per frame (default 68)\n"
            "  --out PATH   output file, '-' for stdout (default led_frames.json)\n"
            "  --speed N    rgb_matrix_config.speed (default %d, the firmware's RGB_MATRIX_DEFAULT_SPD)\n"
            "  --hue/--sat/--val N  rgb_matrix_config.hsv, default %d/%d/%d\n"
            "                       (val defaults to RGB_MATRIX_MAXIMUM_BRIGHTNESS = %d)\n"
            "  --seed N     RNG seed (default %u), fixed so runs are reproducible\n"
            "  --list-modes print the harness' mode numbers and exit\n"
            "  --no-cie     use hsv_to_rgb_nocie() instead of the CIE1931 curve\n"
            "               (the firmware is built with -DUSE_CIE1931_CURVE, so the\n"
            "                default, CIE-curved output is what the LEDs really get)\n",
            argv0, RGB_MATRIX_DEFAULT_SPD, RGB_MATRIX_DEFAULT_HUE, RGB_MATRIX_DEFAULT_SAT, RGB_MATRIX_DEFAULT_VAL, RGB_MATRIX_MAXIMUM_BRIGHTNESS, g_seed);
}

static bool parse_u32(const char *s, uint32_t *out) {
    char *end = NULL;
    long  v   = strtol(s, &end, 10);
    if (end == s || *end != '\0' || v < 0 || v > 0xFFFFFFFFL) return false;
    *out = (uint32_t)v;
    return true;
}

/* QMK's own rgb_matrix_get_mode_name() switch (rgb_matrix.c:824-862), used only
 * by --list-modes so the enum can be inspected/diffed. */
static const char *harness_mode_name(uint8_t mode) {
    switch (mode) {
        case RGB_MATRIX_NONE:
            return "NONE";

#define RGB_MATRIX_EFFECT(name, ...) \
        case RGB_MATRIX_##name:      \
            return #name;
#include "rgb_matrix_effects.inc"
#undef RGB_MATRIX_EFFECT

        default:
            return "UNKNOWN";
    }
}

int main(int argc, char **argv) {
    uint32_t    frames   = 120;
    uint32_t    dt_ms    = 68;
    const char *out_path = "led_frames.json";

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        uint32_t    v;
        if (!strcmp(a, "--list-modes")) {
            for (unsigned m = 0; m < (unsigned)RGB_MATRIX_EFFECT_MAX; m++) {
                printf("%u %s\n", m, harness_mode_name((uint8_t)m));
            }
            printf("RGB_MATRIX_EFFECT_MAX=%u (%u effects enabled in this build)\n", (unsigned)RGB_MATRIX_EFFECT_MAX, (unsigned)RGB_MATRIX_EFFECT_MAX - 1);
            return 0;
        }
        if (!strcmp(a, "--help") || !strcmp(a, "-h")) {
            usage(argv[0]);
            return 0;
        } else if (!strcmp(a, "--frames") && i + 1 < argc) {
            if (!parse_u32(argv[++i], &frames) || frames == 0) {
                fprintf(stderr, "harness: bad --frames\n");
                return 2;
            }
        } else if (!strcmp(a, "--dt-ms") && i + 1 < argc) {
            if (!parse_u32(argv[++i], &dt_ms) || dt_ms == 0 || dt_ms > UINT16_MAX) {
                fprintf(stderr, "harness: bad --dt-ms\n");
                return 2;
            }
        } else if (!strcmp(a, "--out") && i + 1 < argc) {
            out_path = argv[++i];
        } else if (!strcmp(a, "--speed") && i + 1 < argc) {
            if (!parse_u32(argv[++i], &v) || v > UINT8_MAX) {
                fprintf(stderr, "harness: bad --speed\n");
                return 2;
            }
            g_speed = (uint8_t)v;
        } else if (!strcmp(a, "--hue") && i + 1 < argc) {
            if (!parse_u32(argv[++i], &v) || v > UINT8_MAX) {
                fprintf(stderr, "harness: bad --hue\n");
                return 2;
            }
            g_hue = (uint8_t)v;
        } else if (!strcmp(a, "--sat") && i + 1 < argc) {
            if (!parse_u32(argv[++i], &v) || v > UINT8_MAX) {
                fprintf(stderr, "harness: bad --sat\n");
                return 2;
            }
            g_sat = (uint8_t)v;
        } else if (!strcmp(a, "--val") && i + 1 < argc) {
            if (!parse_u32(argv[++i], &v) || v > UINT8_MAX) {
                fprintf(stderr, "harness: bad --val\n");
                return 2;
            }
            g_val = (uint8_t)v;
        } else if (!strcmp(a, "--no-cie")) {
            g_use_cie1931 = false;
        } else if (!strcmp(a, "--seed") && i + 1 < argc) {
            uint32_t s;
            if (!parse_u32(argv[++i], &s)) {
                fprintf(stderr, "harness: bad --seed\n");
                return 2;
            }
            g_seed = s;
        } else {
            fprintf(stderr, "harness: unknown argument '%s'\n", a);
            usage(argv[0]);
            return 2;
        }
    }

    g_frame_dt_ms = dt_ms;

    uint8_t *frames_by_effect[ARRAY_SIZE_OF(k_effects)];
    for (size_t e = 0; e < ARRAY_SIZE_OF(k_effects); e++) {
        frames_by_effect[e] = malloc((size_t)frames * RGB_MATRIX_LED_COUNT * 3);
        if (!frames_by_effect[e]) {
            fprintf(stderr, "harness: out of memory\n");
            return 1;
        }
        run_effect(&k_effects[e], frames, frames_by_effect[e]);
    }

    FILE *fp = stdout;
    if (strcmp(out_path, "-") != 0) {
        fp = fopen(out_path, "w");
        if (!fp) {
            fprintf(stderr, "harness: cannot write %s\n", out_path);
            return 1;
        }
    }
    write_json(fp, frames, dt_ms, frames_by_effect);
    if (fp != stdout) {
        if (fclose(fp) != 0) {
            fprintf(stderr, "harness: error closing %s\n", out_path);
            return 1;
        }
        struct stat st;
        if (stat(out_path, &st) == 0) {
            fprintf(stderr, "wrote %s (%lld bytes)\n", out_path, (long long)st.st_size);
        }
    }
    fflush(stdout);

    /* ---- verification summary (stderr so `--out -` stays pipeable) ---- */
    fprintf(stderr, "\ncie1931=%s seed=%u\n", g_use_cie1931 ? "on (matches firmware)" : "off (--no-cie)", (unsigned)g_seed);
    fprintf(stderr, "led_count=%d frames=%u dt_ms=%u speed=%u hsv=[%u,%u,%u] max_brightness=%d\n", RGB_MATRIX_LED_COUNT, (unsigned)frames, (unsigned)dt_ms, (unsigned)g_speed, (unsigned)g_hue, (unsigned)g_sat, (unsigned)g_val, RGB_MATRIX_MAXIMUM_BRIGHTNESS);
    fprintf(stderr, "%-26s %5s %8s %14s %10s %9s\n", "effect", "mode", "max_ch", "frames!=f0", "nonzero_fr", "lit_leds");
    for (size_t e = 0; e < ARRAY_SIZE_OF(k_effects); e++) {
        const uint8_t *base = frames_by_effect[e];
        unsigned       max_ch = 0, nonzero_frames = 0, diff_frames = 0, lit_leds = 0;
        for (uint32_t f = 0; f < frames; f++) {
            const uint8_t *px        = base + (size_t)f * RGB_MATRIX_LED_COUNT * 3;
            bool           any       = false;
            bool           differs   = false;
            const uint8_t *first     = base; /* frame 0 */
            for (int i = 0; i < RGB_MATRIX_LED_COUNT * 3; i++) {
                if (px[i] > max_ch) max_ch = px[i];
                if (px[i] != 0) any = true;
                if (px[i] != first[i]) differs = true;
            }
            if (any) nonzero_frames++;
            for (int i = 0; i < RGB_MATRIX_LED_COUNT; i++) {
                if (px[i * 3] || px[i * 3 + 1] || px[i * 3 + 2]) lit_leds++;
            }
            if (f > 0 && differs) diff_frames++;
        }
        fprintf(stderr, "%-26s %5u %8u %14u %10u %9u\n", k_effects[e].name, (unsigned)k_effects[e].mode, max_ch, diff_frames, nonzero_frames, lit_leds);
    }

    for (size_t e = 0; e < ARRAY_SIZE_OF(k_effects); e++) free(frames_by_effect[e]);
    return 0;
}
