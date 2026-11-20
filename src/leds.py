"""Logical LED rings mapped onto one or more NeoPixel data lines.

Each Ring has its own RGB buffer indexed logically: 0 = 12 o'clock, increasing
clockwise. Display.show() maps that to physical LEDs (offset/reverse/chain
position), applies brightness + gamma via a lookup table and an estimated
current limit, then pushes the data out.
"""
from array import array
from math import floor

import machine
import micropython
import neopixel

import config
from colors import WHEEL


# Hot loops use the viper emitter (~50x faster than plain Python on the C6).
@micropython.viper
def _map(dst, src, offs, lut, n: int, o0: int, o1: int, o2: int, add: int):
    """dst[led*3 + order] = lut[src[...]] for n LEDs; offs = physical LED numbers.
    With add=1 the result is added (saturating) to what is already in dst, i.e.
    layers are mixed in light space, after brightness/gamma - like real light.

    A faint pixel that would round to black is kept visible at level 1, but only
    in its dominant channel(s), so dim tails keep the hue of the bright head
    instead of turning e.g. red+green = yellow."""
    d = ptr8(dst)
    s = ptr8(src)
    f = ptr16(offs)
    lt = ptr8(lut)
    j = 0
    for i in range(n):
        sr = s[j]
        sg = s[j + 1]
        sb = s[j + 2]
        r = lt[sr]
        g = lt[sg]
        b = lt[sb]
        if r == 0 and g == 0 and b == 0 and (sr | sg | sb):
            m = sr
            if sg > m:
                m = sg
            if sb > m:
                m = sb
            h = m >> 1
            if sr > h:
                r = 1
            if sg > h:
                g = 1
            if sb > h:
                b = 1
        p = f[i] * 3
        if add:
            r += d[p + o0]
            g += d[p + o1]
            b += d[p + o2]
            if r > 255:
                r = 255
            if g > 255:
                g = 255
            if b > 255:
                b = 255
        d[p + o0] = r
        d[p + o1] = g
        d[p + o2] = b
        j += 3


@micropython.viper
def _scale(buf, n: int, k: int):
    """buf[i] = buf[i] * k / 256"""
    b = ptr8(buf)
    for i in range(n):
        b[i] = (b[i] * k) >> 8


def _clamp(v):
    v = int(v)
    return 0 if v < 0 else 255 if v > 255 else v


class Ring:
    def __init__(self, n, offset=0, reverse=False):
        self.n = n
        self.buf = bytearray(3 * n)
        self._zero = bytes(3 * n)
        self.offset = offset % n
        self.reverse = reverse
        self.bg = None

    def background(self):
        """A second Ring underneath this one, for static things like clock ticks.
        It is added to this ring in light space (after gamma), so anything
        drawn over it can only make it brighter. Removed by Display.clear()."""
        if self.bg is None:
            self.bg = Ring(self.n, self.offset, self.reverse)
        return self.bg

    def physical(self, i):
        """Physical LED number (within this ring) for logical position i."""
        i %= self.n
        return (self.offset - i) % self.n if self.reverse else (self.offset + i) % self.n

    def clear(self):
        self.buf[:] = self._zero

    def fill(self, r, g, b):
        r, g, b = _clamp(r), _clamp(g), _clamp(b)
        buf = self.buf
        for j in range(0, len(buf), 3):
            buf[j] = r
            buf[j + 1] = g
            buf[j + 2] = b

    def set(self, i, r, g, b):
        j = (int(i) % self.n) * 3
        buf = self.buf
        buf[j] = _clamp(r)
        buf[j + 1] = _clamp(g)
        buf[j + 2] = _clamp(b)

    def add(self, i, r, g, b):
        """Additive (saturating) draw - overlapping things get brighter."""
        j = (int(i) % self.n) * 3
        buf = self.buf
        buf[j] = _clamp(buf[j] + r)
        buf[j + 1] = _clamp(buf[j + 1] + g)
        buf[j + 2] = _clamp(buf[j + 2] + b)

    def get(self, i):
        j = (int(i) % self.n) * 3
        return self.buf[j], self.buf[j + 1], self.buf[j + 2]

    def hue(self, i, h, level=255):
        """Set LED i to rainbow hue h (0..255, wraps) at the given level."""
        k = (int(h) & 255) * 3
        j = (int(i) % self.n) * 3
        buf = self.buf
        buf[j] = WHEEL[k] * level // 255
        buf[j + 1] = WHEEL[k + 1] * level // 255
        buf[j + 2] = WHEEL[k + 2] * level // 255

    def fade(self, keep):
        """Multiply everything by keep/256 (e.g. 230 = short trails, 250 = long)."""
        _scale(self.buf, len(self.buf), keep)

    def dot(self, pos, r, g, b, radius=1.0):
        """Anti-aliased blob at fractional position pos (in LEDs). Additive."""
        lo = int(floor(pos - radius)) + 1
        hi = int(floor(pos + radius))
        for k in range(lo, hi + 1):
            w = 1.0 - abs(k - pos) / radius
            if w > 0:
                self.add(k, r * w, g * w, b * w)

    def angle_dot(self, turns, r, g, b, radius=1.0):
        """Like dot() but positioned in turns (0..1) so rings line up radially."""
        self.dot(turns * self.n, r, g, b, radius)


class Display:
    def __init__(self):
        self._order = tuple(config.COLOR_ORDER.index(c) for c in "RGB")
        lengths = {}
        for rc in config.RINGS.values():
            end = rc.get("first", 0) + rc["count"]
            lengths[rc["pin"]] = max(lengths.get(rc["pin"], 0), end)
        strips = {}
        for pin, n in lengths.items():
            strips[pin] = (neopixel.NeoPixel(machine.Pin(pin, machine.Pin.OUT), n), [])
        self.rings = {}
        for name, rc in config.RINGS.items():
            ring = Ring(rc["count"], rc.get("offset", 0), rc.get("reverse", False))
            first = rc.get("first", 0)
            offs = array("H", [first + ring.physical(i) for i in range(ring.n)])
            strips[rc["pin"]][1].append((ring, offs))
            self.rings[name] = ring
            setattr(self, name, ring)
        self._strips = list(strips.values())
        self.max_ma = getattr(config, "MAX_CURRENT_MA", 0)
        self._lut = bytearray(256)
        self._brightness = -1
        import state
        self.brightness = state.brightness()   # saved/configured value, night cap

    @property
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, b):
        b = max(0.0, min(1.0, b))
        if b == self._brightness:
            return
        self._brightness = b
        g = config.GAMMA
        lut = self._lut
        for i in range(256):
            lut[i] = int(255 * b * (i / 255) ** g + 0.5)   # faint-pixel floor is in _map

    def clear(self):
        """Clear all rings and drop their background layers."""
        for r in self.rings.values():
            r.clear()
            r.bg = None

    def show(self):
        lut = self._lut
        o0, o1, o2 = self._order
        for np, entries in self._strips:
            for ring, offs in entries:
                _map(np.buf, ring.buf, offs, lut, ring.n, o0, o1, o2, 0)
                if ring.bg is not None:
                    _map(np.buf, ring.bg.buf, offs, lut, ring.n, o0, o1, o2, 1)
        if self.max_ma:
            # ~20 mA per channel at 255; scale everything down if over budget
            ma = sum(sum(np.buf) for np, _ in self._strips) * 20 // 255
            if ma > self.max_ma:
                k = self.max_ma * 256 // ma
                for np, _ in self._strips:
                    _scale(np.buf, len(np.buf), k)
        for np, _ in self._strips:
            np.write()

    def off(self):
        self.clear()
        self.show()
