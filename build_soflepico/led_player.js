/* sofle_pico 灯效互动播放器
 *
 * 数据来自 led_effects.js（gen_led_effects.py 生成），而 led_effects.js 里的每一帧
 * 是 led_effects/harness.c 在本机跑**真实 QMK 灯效源码**算出来的——所以画面上就是
 * 真机会点亮的颜色，不是照着效果图临摹的。
 *
 * 亮度/色相滑块是在这份逐帧数据上做 HSV 换算的预览：固件里 RM_VALU/RM_VALD 改的就是
 * hsv.v（再过一道 CIE1931 亮度曲线）、RM_HUEU/RM_HUED 改的就是 hsv.h，这里的换算和
 * 按键是同一个意思（CIE 曲线表也是从 quantum/led_tables.c 里取的）。
 * 速度滑块则相当于换 RM_SPDU/RM_SPDD。
 */
(function () {
  "use strict";

  var D = window.SOFLE_LED_FX;
  var host = document.getElementById("ledfx");
  if (!D || !host) return;

  // ---- 数据解包 --------------------------------------------------------
  // 每个灯效一段 base64：按帧、按灯（全局 LED 索引）、按 R,G,B 排好
  var effects = D.effects.map(function (e) {
    var bin = atob(e.data);
    var buf = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    e.rgb = buf;
    return e;
  });

  var state = {
    index: 0,
    frame: 0,
    playing: true,
    brightness: D.max_brightness || 255,
    hue: 0,          // 度，-180..180
    speed: 1,
    acc: 0,
    last: 0,
  };

  // ---- DOM -------------------------------------------------------------
  host.innerHTML = "";

  var bar = document.createElement("div");
  bar.className = "fx-bar";
  host.appendChild(bar);

  var buttons = effects.map(function (e, i) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "fx-btn";
    b.textContent = e.title;
    b.title = e.key + " — " + e.desc;
    b.addEventListener("click", function () {
      state.index = i;
      state.frame = 0;
      state.acc = 0;
      paint();
    });
    bar.appendChild(b);
    return b;
  });

  var canvas = document.createElement("canvas");
  canvas.width = D.canvas[0];
  canvas.height = D.canvas[1];
  canvas.className = "fx-canvas";
  var ctx = canvas.getContext("2d");
  host.appendChild(canvas);

  var caption = document.createElement("p");
  caption.className = "fx-caption";
  host.appendChild(caption);

  var controls = document.createElement("div");
  controls.className = "fx-sliders";
  host.appendChild(controls);

  function slider(label, min, max, step, value, fmt, oninput) {
    var wrap = document.createElement("label");
    wrap.className = "fx-slider";
    var span = document.createElement("span");
    span.textContent = label;
    var input = document.createElement("input");
    input.type = "range";
    input.min = min;
    input.max = max;
    input.step = step;
    input.value = value;
    var out = document.createElement("b");
    out.textContent = fmt(value);
    input.addEventListener("input", function () {
      var v = parseFloat(input.value);
      out.textContent = fmt(v);
      oninput(v);
      paint();
    });
    wrap.appendChild(span);
    wrap.appendChild(input);
    wrap.appendChild(out);
    controls.appendChild(wrap);
    return input;
  }

  var playBtn = document.createElement("button");
  playBtn.type = "button";
  playBtn.className = "fx-btn fx-play";
  playBtn.addEventListener("click", function () {
    state.playing = !state.playing;
    state.last = 0;
    playBtn.textContent = state.playing ? "暂停" : "播放";
  });
  playBtn.textContent = "暂停";
  controls.appendChild(playBtn);

  slider("亮度", 0, D.max_brightness || 255, 1, state.brightness,
    function (v) { return v + " / " + (D.max_brightness || 255); },
    function (v) { state.brightness = v; });
  slider("色相", -180, 180, 1, 0,
    function (v) { return (v > 0 ? "+" : "") + v + "°"; },
    function (v) { state.hue = v; });
  slider("速度", 0.25, 3, 0.05, 1,
    function (v) { return v.toFixed(2) + "×"; },
    function (v) { state.speed = v; });

  // ---- 颜色换算（和固件一样在 HSV 空间里调亮度/色相） --------------------
  // 亮度不是线性的：固件编译时带 -DUSE_CIE1931_CURVE，hsv_to_rgb() 会先把 hsv.v 过一遍
  // CIE1931 曲线（v=127 实际只有 47 级），所以这里用同一张表（D.cie，从 quantum/led_tables.c 抠的）。
  var CIE = D.cie;

  function adjust(r, g, b) {
    var max = Math.max(r, g, b), min = Math.min(r, g, b);
    if (max === 0) return "rgb(0,0,0)";
    var s = (max - min) / max;
    var h = 0;
    if (max !== min) {
      var d = max - min;
      if (max === r) h = ((g - b) / d + (g < b ? 6 : 0));
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h *= 60;
    }
    h = (h + state.hue + 360) % 360;
    var v = CIE ? CIE[Math.max(0, Math.min(255, Math.round(state.brightness)))] / 255
                : state.brightness / (D.max_brightness || 255);
    if (v <= 0) return "rgb(0,0,0)";
    var c = v * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = v - c;
    var rr, gg, bb;
    if (h < 60) { rr = c; gg = x; bb = 0; }
    else if (h < 120) { rr = x; gg = c; bb = 0; }
    else if (h < 180) { rr = 0; gg = c; bb = x; }
    else if (h < 240) { rr = 0; gg = x; bb = c; }
    else if (h < 300) { rr = x; gg = 0; bb = c; }
    else { rr = c; gg = 0; bb = x; }
    return "rgb(" + Math.round((rr + m) * 255) + "," + Math.round((gg + m) * 255) +
           "," + Math.round((bb + m) * 255) + ")";
  }

  // Safari 老一点的版本没有 roundRect，自己用 arcTo 画
  function roundRect(c, x, y, w, h, r) {
    if (c.roundRect) { c.beginPath(); c.roundRect(x, y, w, h, r); return; }
    r = Math.min(r, w / 2, h / 2);
    c.beginPath();
    c.moveTo(x + r, y);
    c.arcTo(x + w, y, x + w, y + h, r);
    c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r);
    c.arcTo(x, y, x + w, y, r);
    c.closePath();
  }

  // ---- 画一帧 ----------------------------------------------------------
  function paint() {
    var eff = effects[state.index];
    var base = state.frame * D.led_count * 3;

    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#0a0e12";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 键帽
    ctx.lineWidth = 1;
    ctx.strokeStyle = "#2e3a46";
    ctx.fillStyle = "#171e26";
    for (var i = 0; i < D.leds.length; i++) {
      var k = D.leds[i];
      roundRect(ctx, k.cx - k.w / 2, k.cy - k.h / 2, k.w, k.h, 8);
      ctx.fill();
      ctx.stroke();
    }

    // 灯光：用 shadow 做一层辉光，叠在键帽上
    ctx.globalCompositeOperation = "lighter";
    for (var j = 0; j < D.leds.length; j++) {
      var led = D.leds[j];
      var col = adjust(eff.rgb[base + j * 3], eff.rgb[base + j * 3 + 1], eff.rgb[base + j * 3 + 2]);
      ctx.fillStyle = col;
      ctx.shadowColor = col;
      ctx.shadowBlur = 16;
      roundRect(ctx, led.cx - led.w / 2, led.cy - led.h / 2, led.w, led.h, 8);
      ctx.fill();
    }
    ctx.shadowBlur = 0;
    ctx.globalCompositeOperation = "source-over";

    for (var b = 0; b < buttons.length; b++) {
      buttons[b].classList.toggle("on", b === state.index);
    }
    caption.innerHTML = "<b>" + eff.title + "</b>（<code>" + eff.key + "</code>）—— " +
      eff.desc + " · " + (eff.frames > 1 ? eff.frames + " 帧 / " + D.fps + " fps" : "静态") +
      (eff.id.indexOf("reactive") >= 0 || eff.id.indexOf("heatmap") >= 0
        ? " · 画面里那些涟漪是脚本按固定节奏“打字”打出来的" : "");
  }

  // ---- 循环 ------------------------------------------------------------
  function tick(now) {
    var eff = effects[state.index];
    if (state.playing) {
      if (!state.last) state.last = now;
      state.acc += (now - state.last) * state.speed;
      state.last = now;
      var frameMs = D.dt_ms;
      var guard = 0;
      while (state.acc >= frameMs && guard++ < 240) {
        state.acc -= frameMs;
        state.frame = (state.frame + 1) % eff.frames;
      }
      if (state.acc > frameMs * 240) state.acc = 0;  // 切回来时别追帧追到卡死
      paint();
    } else {
      state.last = 0;
    }
    requestAnimationFrame(tick);
  }

  paint();
  requestAnimationFrame(tick);
})();
