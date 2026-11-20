"""Persistent settings (/state.json) and the single source of truth for brightness.

Brightness = config.BRIGHTNESS, unless changed from the web UI / API since the
last deploy; in night hours it is capped at config.NIGHT. Editing BRIGHTNESS in
config.py and deploying discards the web UI value again.
"""
import json

import config
import timeutil

FILE = "/state.json"


def load():
    s = {"mode": config.DEFAULT_MODE, "brightness": config.BRIGHTNESS}
    try:
        with open(FILE) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return s
    if saved.pop("config_brightness", None) != config.BRIGHTNESS:
        saved.pop("brightness", None)   # config.py changed since: config wins
    s.update(saved)
    return s


def save(s):
    d = dict(s)
    d["config_brightness"] = config.BRIGHTNESS
    try:
        with open(FILE, "w") as f:
            json.dump(d, f)
    except OSError as e:
        print("state save failed:", e)


def is_night():
    n = config.NIGHT
    if not n or not timeutil.synced():
        return False
    h, start, end = timeutil.now()[3], n[0], n[1]
    return (h >= start or h < end) if start > end else (start <= h < end)


def brightness(s=None):
    """Brightness to use right now (saved/configured value, night cap applied)."""
    b = (s or load())["brightness"]
    if is_night():
        b = min(b, config.NIGHT[2])
    return b
