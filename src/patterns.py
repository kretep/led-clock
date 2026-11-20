"""Animations and test patterns.

Every pattern has:
    start(d)        called once when the mode is selected (d = leds.Display)
    render(d, t)    called every frame; t = milliseconds since start
Draw into d.outer (60 LEDs) and d.inner (24 LEDs); the app calls d.show().

Try one over USB without touching the running app:
    make preview P=comets
Add your own: write a class, then append it to PATTERNS at the bottom.
"""
import random
from math import cos, sin

from colors import wheel

TAU = 6.283185


class Pattern:
    def start(self, d):
        d.clear()

    def render(self, d, t):
        pass


class Rainbow(Pattern):
    """Rotating rainbow; the inner ring counter-rotates twice as fast."""

    def render(self, d, t):
        o, i = d.outer, d.inner
        sh = t >> 3
        for k in range(o.n):
            o.hue(k, k * 256 // o.n + sh)
        for k in range(i.n):
            i.hue(k, k * 256 // i.n - 2 * sh)


class Comets(Pattern):
    """Rainbow comets with fading tails, going opposite ways on each ring."""

    def render(self, d, t):
        o, i = d.outer, d.inner
        o.fade(205)
        i.fade(195)
        for c in range(3):
            r, g, b = wheel(t // 25 + c * 85)
            o.dot((t * 0.03 + c * o.n / 3) % o.n, r, g, b)
        for c in range(2):
            r, g, b = wheel(t // 25 + 128 + c * 128)
            i.dot((-t * 0.018 + c * i.n / 2) % i.n, r, g, b)


class Planetary(Pattern):
    """Planetary gear: teeth move at the same linear speed, so the small ring
    spins 2.5x faster - like a pinion rolling inside a ring gear."""

    def render(self, d, t):
        shift = t / 110
        hue = t // 40
        self._gear(d.outer, shift, 6, hue)
        self._gear(d.inner, shift, 6, hue + 128)

    @staticmethod
    def _gear(ring, shift, period, hue):
        half, quarter = period / 2, period / 4
        for k in range(ring.n):
            x = k + shift
            ph = x % period
            w = 1 - abs(ph - half) / quarter
            if w > 0:
                ring.hue(k, hue + int(x // period) * 30, int(255 * w))
            else:
                ring.set(k, 0, 0, 0)


class Sparkle(Pattern):
    """Random rainbow twinkles that fade out."""

    def render(self, d, t):
        rnd = random.getrandbits
        for ring, n_new in ((d.outer, 2), (d.inner, 1)):
            ring.fade(232)
            for _ in range(n_new):
                if rnd(8) < 110:
                    r, g, b = wheel(rnd(8))
                    ring.set(rnd(8) % ring.n, r, g, b)


class Plasma(Pattern):
    """Flowing plasma; both rings sample the same field so colours line up radially."""

    def render(self, d, t):
        ts = t / 1000
        for ring, rad in ((d.outer, 1.0), (d.inner, 0.42)):
            n = ring.n
            for k in range(n):
                a = TAU * k / n
                v = sin(a * 2 + ts * 1.3) + sin(a * 3 - ts * 0.7 + rad * 4) + sin(rad * 5 + ts)
                ring.hue(k, int(v * 42 + ts * 25))


class Breathe(Pattern):
    """Slow breathing; complementary hues on the two rings."""

    def render(self, d, t):
        x = (1 - cos(t * 0.0021)) / 2
        lvl = int(6 + 249 * x * x)
        h = t // 80
        r, g, b = wheel(h, lvl)
        d.outer.fill(r, g, b)
        r, g, b = wheel(h + 128, lvl)
        d.inner.fill(r, g, b)


class Chase(Pattern):
    """Rainbow theatre chase."""

    def render(self, d, t):
        step = t // 70
        for ring, direction in ((d.outer, 1), (d.inner, -1)):
            n = ring.n
            for k in range(n):
                if (k + step * direction) % 3 == 0:
                    ring.hue(k, k * 256 // n + t // 15)
                else:
                    ring.set(k, 0, 0, 0)


class Wipe(Pattern):
    """Colour wipes through the rainbow, the inner ring wiping the other way."""
    PERIOD = 1400

    def render(self, d, t):
        c, rem = divmod(t, self.PERIOD)
        frac = rem / self.PERIOD
        new, old = wheel(c * 37), wheel((c - 1) * 37)
        for ring, rev in ((d.outer, False), (d.inner, True)):
            n = ring.n
            edge = frac * n
            for k in range(n):
                kk = n - 1 - k if rev else k
                w = edge - k
                if w >= 1:
                    ring.set(kk, *new)
                elif w <= 0:
                    ring.set(kk, *old)
                else:
                    ring.set(kk, *(old[j] + (new[j] - old[j]) * w for j in range(3)))


class Radar(Pattern):
    """Sweeping radar beam with afterglow and the occasional blip."""

    def render(self, d, t):
        a = (t % 3000) / 3000
        d.outer.fade(247)
        d.inner.fade(247)
        d.outer.angle_dot(a, 0, 255, 70, 1.5)
        d.inner.angle_dot(a, 0, 255, 70, 1.0)
        if random.getrandbits(8) < 6:
            ring = d.outer if random.getrandbits(1) else d.inner
            ring.set(random.getrandbits(8) % ring.n, 255, 140, 0)


class Fire(Pattern):
    """Flickering embers."""

    def start(self, d):
        d.clear()
        self.heat = [bytearray(d.outer.n), bytearray(d.inner.n)]

    def render(self, d, t):
        rnd = random.getrandbits
        for ring, heat in ((d.outer, self.heat[0]), (d.inner, self.heat[1])):
            for k in range(ring.n):
                h = heat[k] - (rnd(4) + 2)
                if rnd(8) < 9:
                    h = 160 + rnd(6)
                h = 0 if h < 0 else 255 if h > 255 else h
                heat[k] = h
                # black -> red -> orange -> yellow
                ring.set(k, min(255, h * 2), max(0, h * 2 - 200) if h > 100 else 0, 0)
                if h > 200:
                    ring.add(k, 0, 80, (h - 200) * 2)


class Calibrate(Pattern):
    """Ring calibration: logical LED 0 = RED (should be 12 o'clock), next three
    GREEN (should go clockwise), quarter marks dim BLUE, white dot walks around.

    With offset=0, reverse=False the red LED is physical LED 0. Count the LEDs
    from red to 12 o'clock in the direction the green LEDs point: that count is
    `offset`. If the green LEDs run anticlockwise, set reverse=True as well."""

    def render(self, d, t):
        for ring in (d.outer, d.inner):
            ring.clear()
            q = ring.n // 4
            for k in range(q, ring.n, q):
                ring.set(k, 0, 0, 60)
            ring.set(0, 255, 0, 0)
            ring.set(1, 0, 220, 0)
            ring.set(2, 0, 90, 0)
            ring.set(3, 0, 30, 0)
            ring.add((t // 200) % ring.n, 50, 50, 50)


class RGBTest(Pattern):
    """Solid red, green, blue, white, then a static rainbow. If 'red' shows as
    green, your COLOR_ORDER is wrong (try "RGB")."""
    STEPS = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255), None)

    def render(self, d, t):
        c = self.STEPS[(t // 1500) % len(self.STEPS)]
        for ring in (d.outer, d.inner):
            if c:
                ring.fill(*c)
            else:
                for k in range(ring.n):
                    ring.hue(k, k * 256 // ring.n)


class Demo(Pattern):
    """Cycles through the showcase patterns."""
    PERIOD = 15000

    def start(self, d):
        d.clear()
        self.idx = -1

    def render(self, d, t):
        idx = (t // self.PERIOD) % len(SHOWCASE)
        if idx != self.idx:
            self.idx = idx
            self.cur = SHOWCASE[idx]()
            self.cur.start(d)
            self.t_start = t
        self.cur.render(d, t - self.t_start)


SHOWCASE = [Rainbow, Comets, Planetary, Plasma, Sparkle, Chase, Wipe, Radar, Breathe, Fire]

# (mode name, class) - order is the order the BOOT button cycles through.
PATTERNS = [
    ("demo", Demo),
    ("rainbow", Rainbow),
    ("comets", Comets),
    ("planetary", Planetary),
    ("plasma", Plasma),
    ("sparkle", Sparkle),
    ("chase", Chase),
    ("wipe", Wipe),
    ("radar", Radar),
    ("breathe", Breathe),
    ("fire", Fire),
    ("calibrate", Calibrate),
    ("rgbtest", RGBTest),
]


def preview(name="demo", seconds=0, brightness=None):
    """Run one pattern in the foreground (USB REPL / mpremote). Ctrl-C to stop."""
    import time
    import config
    from leds import Display
    d = Display()
    if brightness is not None:
        d.brightness = brightness
    p = dict(PATTERNS)[name]()
    p.start(d)
    frame = 1000 // config.FPS
    t0 = time.ticks_ms()
    try:
        while True:
            now = time.ticks_ms()
            el = time.ticks_diff(now, t0)
            if seconds and el > seconds * 1000:
                break
            p.render(d, el)
            d.show()
            spent = time.ticks_diff(time.ticks_ms(), now)
            time.sleep_ms(max(1, frame - spent))
    finally:
        d.off()
