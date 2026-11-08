"""Wi-Fi connection helper for the ESP32-S3.

connect() блокирует выполнение (годится только при старте, если нужно).
maintain() вызывается в основном цикле и НИКОГДА не блокирует его: он лишь
запускает попытку подключения и на следующих кадрах проверяет результат.
"""

import time
import network
import config


class WiFiManager:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.connected = False
        self.connecting = False
        self.last_attempt = None

    def connect(self):
        """Блокирующее подключение (только для ручного вызова)."""
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
        return True

    def maintain(self):
        """Неблокирующая поддержка соединения. Вызывать каждый кадр."""
        if self.wlan.isconnected():
            self.connected = True
            self.connecting = False
            return True

        self.connected = False
        if not config.WIFI_SSID:
            return False

        now = time.ticks_ms()

        if self.connecting:
            # Ждём результат, не блокируя; по таймауту сдаёмся до следующей попытки
            if time.ticks_diff(now, self.last_attempt) >= config.WIFI_CONNECT_TIMEOUT_MS:
                self.connecting = False
            return False

        if (self.last_attempt is None
                or time.ticks_diff(now, self.last_attempt) >= config.WIFI_RETRY_MS):
            self.last_attempt = now
            self.wlan.active(True)
            self.wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
            self.connecting = True
        return False

    def status(self):
        return {
            "connected": self.connected,
            "ip": self.wlan.ifconfig()[0] if self.wlan.isconnected() else None,
        }
