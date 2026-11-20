"""The LED clock application: mode manager, render loop, NTP, button, web API."""
import asyncio
import gc
import time

from machine import Pin

import clockfaces
import config
import ota
import patterns
import state
import timeutil
from leds import Display

MODES = clockfaces.FACES + patterns.PATTERNS
MODE_NAMES = [name for name, _ in MODES]
_MODE_CLS = dict(MODES)


class App:
    def __init__(self, server=None, wlan=None):
        self.wlan = wlan
        self.d = Display()
        self.state = state.load()
        self.mode_name = None
        if not self.set_mode(self.state["mode"], save=False):
            self.set_mode(config.DEFAULT_MODE, save=False)
        self._apply_brightness()
        if server:
            self._routes(server)

    # --- state -------------------------------------------------------------
    def set_mode(self, name, save=True):
        cls = _MODE_CLS.get(name)
        if cls is None:
            return False
        mode = cls()
        mode.start(self.d)
        self.mode, self.mode_name, self.t0 = mode, name, time.ticks_ms()
        print("mode:", name)
        if save and self.state.get("mode") != name:
            self.state["mode"] = name
            state.save(self.state)
        return True

    def next_mode(self, step=1):
        i = MODE_NAMES.index(self.mode_name) if self.mode_name in MODE_NAMES else 0
        self.set_mode(MODE_NAMES[(i + step) % len(MODE_NAMES)])

    def set_brightness(self, b):
        b = max(0.0, min(config.MAX_BRIGHTNESS, float(b)))
        self.state["brightness"] = b
        self._apply_brightness()
        state.save(self.state)
        return b

    def _apply_brightness(self):
        self.d.brightness = state.brightness(self.state)

    def status(self):
        ts = None
        if timeutil.synced():
            y, mo, dd, h, mi, s, _ = timeutil.now()
            ts = "%04d-%02d-%02d %02d:%02d:%02d" % (y, mo, dd, h, mi, s)
        import wifi
        return {"mode": self.mode_name, "modes": MODE_NAMES,
                "brightness": self.state["brightness"], "max_brightness": config.MAX_BRIGHTNESS,
                "night": state.is_night(), "time": ts, "ip": wifi.ip(self.wlan),
                "uptime_s": ota.uptime_s(), "mem_free": gc.mem_free()}

    # --- web API -----------------------------------------------------------
    def _routes(self, s):
        def page(q, b):
            import webui
            return 200, webui.PAGE, "text/html"

        def mode(q, b):
            name = q.get("name", "")
            if name == "next":
                self.next_mode()
                return 200, {"mode": self.mode_name}
            if self.set_mode(name):
                return 200, {"mode": name}
            return 400, {"error": "unknown mode", "modes": MODE_NAMES}

        def brightness(q, b):
            try:
                return 200, {"brightness": self.set_brightness(q.get("value"))}
            except (TypeError, ValueError):
                return 400, {"error": "value must be a number 0..%s" % config.MAX_BRIGHTNESS}

        s.route("GET", "/", page)
        s.route("GET", "/api/status", lambda q, b: (200, self.status()))
        s.route("POST", "/api/mode", mode)
        s.route("POST", "/api/brightness", brightness)

    # --- tasks -------------------------------------------------------------
    async def render_loop(self):
        frame = 1000 // config.FPS
        d = self.d
        while True:
            t = time.ticks_ms()
            try:
                self.mode.render(d, time.ticks_diff(t, self.t0))
                d.show()
            except Exception as e:
                ota.log_exception(e, "mode '%s' failed" % self.mode_name)
                if self.mode_name == config.DEFAULT_MODE:
                    raise
                self.set_mode(config.DEFAULT_MODE, save=False)
            spent = time.ticks_diff(time.ticks_ms(), t)
            await asyncio.sleep_ms(frame - spent if spent < frame else 1)

    async def ntp_loop(self):
        while True:
            delay = 5
            if self.wlan and self.wlan.isconnected():
                try:
                    timeutil.sync()
                    print("NTP synced:", timeutil.now())
                    delay = 6 * 3600
                except Exception as e:
                    print("NTP failed:", e)
                    delay = 30
            await asyncio.sleep(delay)

    async def button_loop(self):
        btn = Pin(config.BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        while True:
            if btn.value() == 0:
                t0 = time.ticks_ms()
                while btn.value() == 0:
                    await asyncio.sleep_ms(20)
                held = time.ticks_diff(time.ticks_ms(), t0)
                if held > 800:
                    self.set_mode(config.DEFAULT_MODE)
                elif held > 40:
                    self.next_mode()
            await asyncio.sleep_ms(30)

    async def housekeeping_loop(self):
        while True:
            self._apply_brightness()
            await asyncio.sleep(1)


async def run(server=None, wlan=None):
    app = App(server, wlan)
    asyncio.create_task(app.ntp_loop())
    asyncio.create_task(app.button_loop())
    asyncio.create_task(app.housekeeping_loop())
    await app.render_loop()
