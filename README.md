# LED Clock

XIAO ESP32-C6 + MicroPython driving a 60-LED ring (minutes/seconds) and a 24-LED ring (hours), with
over-the-air (OTA) updates over Wi-Fi, a small web UI, and a set of rainbow animations.

## Layout

```
src/                      everything here is copied to the board's root
  main.py                 bootstrap: Wi-Fi + OTA server first, then the app (crash-safe)
  app.py                  mode manager, render loop, NTP, BOOT button, web API
  clockfaces.py           clock faces: clock, clock_rainbow
  patterns.py             animations + test patterns (add your own here)
  leds.py                 Ring/Display: logical rings, brightness, gamma, current limit
  colors.py               hsv / rainbow wheel helpers
  timeutil.py             NTP + time zone / DST
  ota.py                  tiny async HTTP server (OTA + API)
  wifi.py, webui.py
  config.py               pins, ring orientation, time zone, brightness...
  credentials.example.py  copy to credentials.py (git-ignored)
tools/ota.py              OTA deploy/control from your computer (stdlib only)
experiments/sandbox.py    scratch pad: run animations from your laptop without deploying
```

## First-time setup (USB)

1. `cp src/credentials.example.py src/credentials.py` and fill in Wi-Fi + an `OTA_TOKEN`.
2. In `src/config.py` set the data pins in `RINGS` (default: 60-ring on **D0**, 24-ring on **D1**;
   for one daisy-chained line use the same pin and `first=60` for the inner ring), plus
   `TZ_OFFSET_MIN` / `DST_RULE` (e.g. `60` / `"EU"` for Central Europe).
3. Close any open `mpremote repl`, then `make install`.
4. `make repl` shows the boot log, including `Wi-Fi up: http://<ip>/`.

## Daily workflow (Wi-Fi)

```
make ota                                   # push changed files, reboot, wait until it's back
python3 tools/ota.py mode                  # list modes (* = current)
python3 tools/ota.py mode comets
python3 tools/ota.py brightness 0.3
python3 tools/ota.py log                   # last crash traceback
python3 tools/ota.py info                  # firmware, memory, uptime
```

Or open `http://ledclock.local/` on your phone for mode buttons and a brightness slider.
The **BOOT** button cycles modes; a long press returns to the clock.

**Crash safety:** `main.py` starts Wi-Fi and the OTA server *before* importing the app. If `app.py`
or a pattern crashes, the board stays online (the yellow LED blinks) and you can push a fix. A
pattern that throws an error just falls back to the clock. `push` syntax-checks every file before
uploading anything. Only a broken `main.py`, `ota.py`, `wifi.py` or `config.py` needs USB to recover.

## Experimenting with patterns

- `make preview P=plasma [B=0.1]`: run one pattern over USB, using the code in your local `src/`
  folder (nothing is copied to the board).
- `make sandbox`: run `experiments/sandbox.py` on the board straight from your laptop. Edit
  `frame(t)` and re-run; nothing is written to flash.
- Press **Ctrl-C** to stop either one: it stops the animation on the board and turns the LEDs off.
  If the LEDs are ever left running or frozen (for example after a plain `mpremote` Ctrl-C), run
  `make stop`. `make reset` alone leaves them frozen on the last frame.
- To make it permanent, add a class with `render(self, d, t)` to `src/patterns.py`, register it in
  `PATTERNS`, then `make ota`.

Drawing API (`d.outer` = 60 ring, `d.inner` = 24 ring; index 0 = 12 o'clock, clockwise):
`set(i, r, g, b)`, `add(...)`, `hue(i, h, level)`, `fill(...)`, `clear()`, `fade(keep)`,
`dot(pos, r, g, b, radius)` (anti-aliased, fractional positions), `angle_dot(turns, ...)`.

Modes: `clock`, `clock_rainbow`, `demo`, `rainbow`, `comets`, `planetary`, `plasma`, `sparkle`,
`chase`, `wipe`, `radar`, `breathe`, `fire`, plus the diagnostics `calibrate` and `rgbtest`.

## Calibrating the rings

Select `calibrate`. On each ring the red LED is logical 0 and should sit at 12 o'clock; the green
LEDs after it should run clockwise. With `offset=0`, count the LEDs from the red one to 12 o'clock
in the direction the green ones point: that count is `offset`. If green runs anticlockwise,
also set `reverse=True`. Use `rgbtest` to check `COLOR_ORDER`: the first colour shown must be red.

## Brightness

One brightness applies to everything: the clock faces, the animations, `make preview` and
`make sandbox`. It comes from `BRIGHTNESS` in `config.py`. If you change it with the web slider
or the API, that value is kept across reboots, until you change `BRIGHTNESS` in `config.py` and
deploy again; then the config value wins. Between the `NIGHT` hours it is capped at the night level.
`make preview ... B=0.3` overrides it for a single preview.

## Power

84 LEDs at full white draw about 5 A. `MAX_CURRENT_MA` (default 900 mA) scales the output down
when the estimated draw is higher, and `BRIGHTNESS` defaults to 0.25. Raise these only with a
proper 5 V supply. Feed the rings 5 V, connect the grounds together, and ideally put a ~330 Ω
resistor in each data line.
