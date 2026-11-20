# Bootstrap. Keep this file small and stable: it brings up Wi-Fi and the OTA
# server *before* importing the app, so if a pushed app/pattern file crashes,
# the board stays reachable and you can push a fix over Wi-Fi.
import asyncio

import machine

import config


async def _error_blink():
    led = machine.Pin(config.STATUS_LED_PIN, machine.Pin.OUT)
    while True:
        led(not led())
        await asyncio.sleep_ms(200)


async def main():
    import ota
    import wifi

    server = wlan = None
    try:
        import credentials
        wlan = wifi.start(credentials.WIFI_SSID, credentials.WIFI_PASSWORD, config.HOSTNAME)
        asyncio.create_task(wifi.keepalive(wlan, credentials.WIFI_SSID, credentials.WIFI_PASSWORD))
        server = ota.Server(credentials.OTA_TOKEN, config.HTTP_PORT)
        await server.start()
    except ImportError:
        print("credentials.py missing: Wi-Fi and OTA disabled")
    except Exception as e:
        ota.log_exception(e, "network setup failed")

    try:
        import app
        await app.run(server, wlan)
    except Exception as e:
        ota.log_exception(e, "app crashed")
        try:
            from leds import Display
            Display().off()
        except Exception:
            pass
        await _error_blink()  # never returns; OTA server keeps serving


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
