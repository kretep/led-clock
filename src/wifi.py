"""Wi-Fi station setup with automatic reconnect."""
import asyncio
import time

import network
from machine import Pin

import config


def _antenna():
    # XIAO ESP32-C6 RF switch: GPIO3 low enables it, GPIO14 selects the antenna.
    Pin(3, Pin.OUT, value=0)
    Pin(14, Pin.OUT, value=1 if config.EXTERNAL_ANTENNA else 0)


def start(ssid, password, hostname=None):
    """Start connecting (non-blocking) and return the WLAN object."""
    _antenna()
    if hostname:
        try:
            network.hostname(hostname)
        except Exception as e:
            print("hostname:", e)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(pm=wlan.PM_NONE)  # no power save: snappier HTTP/OTA
    except Exception:
        pass
    if not wlan.isconnected():
        wlan.connect(ssid, password)
    return wlan


def ip(wlan):
    return wlan.ifconfig()[0] if wlan and wlan.isconnected() else None


async def keepalive(wlan, ssid, password):
    was_up = False
    down_since = time.ticks_ms()
    while True:
        up = wlan.isconnected()
        if up and not was_up:
            print("Wi-Fi up: http://%s/  (http://%s.local/)" % (ip(wlan), config.HOSTNAME))
        elif was_up and not up:
            print("Wi-Fi lost")
            down_since = time.ticks_ms()
        elif not up and time.ticks_diff(time.ticks_ms(), down_since) > 20000:
            print("Wi-Fi: retrying", ssid)
            try:
                wlan.disconnect()
                wlan.connect(ssid, password)
            except Exception as e:
                print("Wi-Fi:", e)
            down_since = time.ticks_ms()
        was_up = up
        await asyncio.sleep(1)
