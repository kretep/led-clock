"""Colour helpers. Hues are 0..255 (wrapping)."""


def hsv(h, s=255, v=255):
    """Integer HSV -> (r, g, b); all inputs 0..255."""
    h &= 255
    if s == 0:
        return v, v, v
    region = h // 43
    rem = (h - region * 43) * 6
    p = (v * (255 - s)) >> 8
    q = (v * (255 - ((s * rem) >> 8))) >> 8
    t = (v * (255 - ((s * (255 - rem)) >> 8))) >> 8
    if region == 0:
        return v, t, p
    if region == 1:
        return q, v, p
    if region == 2:
        return p, v, t
    if region == 3:
        return p, q, v
    if region == 4:
        return t, p, v
    return v, p, q


# Pre-computed fully saturated rainbow: WHEEL[3*h : 3*h+3] = (r, g, b)
WHEEL = bytearray(768)
for _h in range(256):
    WHEEL[3 * _h], WHEEL[3 * _h + 1], WHEEL[3 * _h + 2] = hsv(_h)
del _h


def wheel(h, level=255):
    """Rainbow colour for hue h, scaled to level (0..255)."""
    j = (int(h) & 255) * 3
    if level >= 255:
        return WHEEL[j], WHEEL[j + 1], WHEEL[j + 2]
    return WHEEL[j] * level // 255, WHEEL[j + 1] * level // 255, WHEEL[j + 2] * level // 255


def scale(c, level):
    """Scale an (r, g, b) tuple by level/255."""
    return c[0] * level // 255, c[1] * level // 255, c[2] * level // 255


def blend(a, b, t):
    """Mix colours a -> b, t = 0..255."""
    u = 255 - t
    return (a[0] * u + b[0] * t) // 255, (a[1] * u + b[1] * t) // 255, (a[2] * u + b[2] * t) // 255
