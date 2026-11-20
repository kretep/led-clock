"""NTP sync and local time with a simple fixed-offset + DST rule."""
import time

import config

_cache_hour = None
_cache_offset = 0


def sync(host=None):
    import ntptime
    ntptime.host = host or config.NTP_HOST
    if hasattr(ntptime, "timeout"):
        ntptime.timeout = 2
    ntptime.settime()  # sets the RTC to UTC


def synced():
    return time.gmtime()[0] >= 2024


def _utc_ms():
    try:
        return time.time_ns() // 1000000
    except AttributeError:
        return time.time() * 1000


def _day(y, m, d):
    return time.mktime((y, m, d, 0, 0, 0, 0, 0))


def _last_sunday(y, m):
    t = _day(y, m + 1, 1) - 86400            # last day of month m
    return t - ((time.gmtime(t)[6] + 1) % 7) * 86400   # gmtime weekday: Mon=0 .. Sun=6


def _nth_sunday(y, m, n):
    t = _day(y, m, 1)
    return t + ((6 - time.gmtime(t)[6]) % 7) * 86400 + (n - 1) * 7 * 86400


def utc_offset(utc_s):
    """Offset from UTC in seconds at UTC time utc_s (cached per hour)."""
    global _cache_hour, _cache_offset
    hour = utc_s // 3600
    if hour == _cache_hour:
        return _cache_offset
    base = config.TZ_OFFSET_MIN * 60
    rule = config.DST_RULE
    off = base
    if rule:
        y = time.gmtime(utc_s)[0]
        if rule == "EU":       # 01:00 UTC on the last Sundays of March and October
            start = _last_sunday(y, 3) + 3600
            end = _last_sunday(y, 10) + 3600
        elif rule == "US":     # 02:00 local on 2nd Sunday March .. 1st Sunday November
            start = _nth_sunday(y, 3, 2) + 7200 - base
            end = _nth_sunday(y, 11, 1) + 7200 - base - 3600
        else:
            raise ValueError("unknown DST_RULE " + str(rule))
        if start <= utc_s < end:
            off += 3600
    _cache_hour, _cache_offset = hour, off
    return off


def now():
    """Local time as (year, month, day, hour, minute, second, millisecond)."""
    ms = _utc_ms()
    s = ms // 1000
    t = time.gmtime(s + utc_offset(s))
    return t[0], t[1], t[2], t[3], t[4], t[5], ms % 1000
