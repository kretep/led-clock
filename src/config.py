"""Device configuration. Edit, then deploy with `make ota` (Wi-Fi) or `make install` (USB)."""

# --- Network -----------------------------------------------------------------
HOSTNAME = "ledclock"          # reachable as http://ledclock.local (mDNS)
HTTP_PORT = 80                 # web UI + OTA endpoint

# --- Time --------------------------------------------------------------------
NTP_HOST = "pool.ntp.org"
TZ_OFFSET_MIN = 60             # standard (winter) offset from UTC in minutes: 60 = CET, -300 = US Eastern
DST_RULE = "EU"                # None, "EU" (last Sun Mar..Oct) or "US" (2nd Sun Mar..1st Sun Nov)
HOUR_RING_24H = False          # False: 24-LED ring is a 12 h dial (2 LEDs per hour). True: 24 h dial.

# --- LED hardware ------------------------------------------------------------
# XIAO ESP32-C6 pad -> GPIO number
D0, D1, D2, D3, D4, D5, D6, D7, D8, D9, D10 = 0, 1, 2, 21, 22, 23, 16, 17, 19, 20, 18

# Each ring: data pin, index of its first LED on that pin's chain, LED count,
#   offset  = physical LED number (0-based) that sits at 12 o'clock,
#   reverse = True if the physical numbering runs anticlockwise.
# Use the "calibrate" mode to find offset/reverse.
# If both rings are daisy-chained on ONE data line (60 first), use
#   "inner": dict(pin=D0, first=60, count=24, ...)
# The names "outer" and "inner" are used by the clock faces and patterns.
RINGS = {
    "outer": dict(pin=D0, first=0, count=60, offset=38, reverse=False),   # 60 LEDs: minutes/seconds
    "inner": dict(pin=D0, first=60, count=24, offset=15, reverse=False),   # 24 LEDs: hours
}
COLOR_ORDER = "GRB"            # WS2812B / SK6812 are GRB. Check with the "rgbtest" mode.

FPS = 40
BRIGHTNESS = 0.1               # 0..1 default brightness
MAX_BRIGHTNESS = 0.8           # upper limit for the web UI / API
GAMMA = 2.0                    # perceptual correction; 1.0 = off
MAX_CURRENT_MA = 900           # estimated-current limiter (~20 mA per channel at full). 0 = off.
NIGHT = (23, 7, 0.04)          # (from hour, until hour, brightness) or None

# --- Clock colours (r, g, b) -------------------------------------------------
COLOR_HOUR = (0, 255, 0)
COLOR_MINUTE = (0, 255, 0)
COLOR_SECOND = (255, 50, 0)     # warm red, leaning orange
COLOR_MARKER = (28, 28, 28)
COLOR_MARKER_12 = (90, 90, 90)

# --- Misc --------------------------------------------------------------------
DEFAULT_MODE = "clock"
BUTTON_PIN = 9                 # BOOT button: short press = next mode, long press = back to clock
STATUS_LED_PIN = 15            # yellow user LED (active low); blinks if the app crashed
EXTERNAL_ANTENNA = False       # XIAO RF switch: True = u.FL connector, False = on-board ceramic antenna
