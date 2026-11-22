"""Clock faces. Same interface as patterns: start(d) / render(d, t)."""
import config
import timeutil


def hour_pos(h, m, n):
    """Fractional LED position of the hour hand on an n-LED ring."""
    if config.HOUR_RING_24H:
        return (h + m / 60) * n / 24
    return ((h % 12) + m / 60) * n / 12


def waiting(d, t):
    """Shown until the time has been synced over NTP."""
    d.outer.fade(200)
    d.inner.fade(200)
    d.outer.dot((t / 40) % d.outer.n, 0, 40, 255)
    d.inner.dot((-t / 100) % d.inner.n, 0, 40, 255)


class Classic:
    """Outer: markers every 5 minutes, minute dot, smooth seconds sweep with tail.
    Inner: just the hour dot. The markers live on the ring's background layer,
    so hands passing over them add light instead of replacing it."""

    def start(self, d):
        d.clear()
        self.markers = False

    @staticmethod
    def _draw_markers(ring):
        bg = ring.background()
        bg.clear()
        for k in range(0, 60, 5):
            bg.set(k, *config.COLOR_MARKER)

    def render(self, d, t):
        if not timeutil.synced():
            return waiting(d, t)
        _, _, _, h, m, s, ms = timeutil.now()
        o, i = d.outer, d.inner
        if not self.markers:
            self._draw_markers(o)
            self.markers = True
        o.clear()
        i.clear()

        sec = s + ms / 1000
        if config.SMOOTH_HANDS:
            o.dot(m + sec / 60, *config.COLOR_MINUTE)
        else:
            o.add(m, *config.COLOR_MINUTE)          # exactly one LED

        r, g, b = config.COLOR_SECOND
        o.dot(sec, r, g, b)
        for k in range(1, 5):
            f = 0.45 / k
            o.dot(sec - k * 0.6, r * f, g * f, b * f)

        hp = hour_pos(h, m, i.n)
        if config.SMOOTH_HANDS:
            i.dot(hp, *config.COLOR_HOUR)
        else:
            i.add(int(hp), *config.COLOR_HOUR)      # one LED; 12 h dial: steps every half hour


class RainbowFace:
    """Minutes fill the outer ring as a rainbow arc, hours fill the inner ring,
    seconds are a white spark."""

    def start(self, d):
        d.clear()

    def render(self, d, t):
        if not timeutil.synced():
            return waiting(d, t)
        _, _, _, h, m, s, ms = timeutil.now()
        o, i = d.outer, d.inner
        drift = t // 60
        for k in range(o.n):
            if k <= m:
                o.hue(k, k * 4 + drift, 70 if k < m else 255)
            else:
                o.set(k, 0, 0, 0)
        hp = hour_pos(h, m, i.n)
        for k in range(i.n):
            if k <= hp:
                i.hue(k, k * 256 // i.n + drift, 80)
            else:
                i.set(k, 0, 0, 0)
        i.dot(hp, 160, 160, 160)
        o.dot(s + ms / 1000, 200, 200, 200)


FACES = [
    ("clock", Classic),
    ("clock_rainbow", RainbowFace),
]
