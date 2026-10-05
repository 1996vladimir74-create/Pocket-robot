"""Wi-Fi connection helper for the ESP32-S3."""

import time
import network
import config


class WiFiManager:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.connected = False
        self.last_attempt = 0

    def connect(self):
        if not config.WIFI_SSID:
            self.connected = False
            return False

        self.wlan.active(True)
        if self.wlan.isconnected():
            self.connected = True
            return True

        self.wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        start = time.ticks_ms()
        while not self.wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) >= config.WIFI_CONNECT_TIMEOUT_MS:
                self.connected = False
                return False
            time.sleep_ms(100)

        self.connected = True
        self.last_attempt = time.ticks_ms()
        return True

    def maintain(self):
        if self.wlan.isconnected():
            self.connected = True
            return True
        self.connected = False
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_attempt) >= config.WIFI_RETRY_MS:
            self.last_attempt = now
            return self.connect()
        return False

    def status(self):
        return {
            "connected": self.connected,
            "ip": self.wlan.ifconfig()[0] if self.wlan.isconnected() else None,
        }
