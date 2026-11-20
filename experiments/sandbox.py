"""Scratch pad for trying animations straight from your laptop - no deploy needed.

    make sandbox        (= mpremote run experiments/sandbox.py)

The file is sent to the board and run there; it uses leds.py / colors.py that
are already installed on the board. Ctrl-C (or Ctrl-]) leaves mpremote; then
`make reset` brings the clock back. When you like something, turn it into a
class in src/patterns.py and add it to PATTERNS.
"""
import random
import time
from math import sin

from colors import hsv, wheel
from leds import Display

d = Display()                # uses the clock's brightness; override with d.brightness = 0.3
o, i = d.outer, d.inner     # 60-LED and 24-LED rings, index 0 = 12 o'clock


def frame(t):
    """t = ms since start. Draw into o / i; d.show() is called for you."""
    # Example: two rainbow "pendulums" swinging on each ring + white sparkles
    o.fade(220)
    i.fade(220)
    swing = sin(t / 600)
    o.dot(30 + 28 * swing, *wheel(t // 30), radius=2.0)
    i.dot(12 - 11 * swing, *wheel(t // 30 + 128), radius=1.5)
    if random.getrandbits(8) < 30:
        o.set(random.getrandbits(8) % 60, 120, 120, 120)


t0 = time.ticks_ms()
try:
    while True:
        t = time.ticks_diff(time.ticks_ms(), t0)
        frame(t)
        d.show()
        time.sleep_ms(20)
finally:
    d.off()
