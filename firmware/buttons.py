"""Three debounced active-low buttons."""

from machine import Pin
import time
import config


class Buttons:
    def __init__(self):
        self.pins = {
            "back": Pin(config.BUTTON_BACK, Pin.IN, Pin.PULL_UP),
            "mode": Pin(config.BUTTON_MODE, Pin.IN, Pin.PULL_UP),
            "action": Pin(config.BUTTON_ACTION, Pin.IN, Pin.PULL_UP),
        }
        self.last_state = {name: 1 for name in self.pins}
        self.last_change = {name: 0 for name in self.pins}

    def poll(self, now_ms=None):
        if now_ms is None:
            now_ms = time.ticks_ms()
        events = []
        for name, pin in self.pins.items():
            state = pin.value()
            if state != self.last_state[name]:
                if time.ticks_diff(now_ms, self.last_change[name]) >= config.BUTTON_DEBOUNCE_MS:
                    self.last_change[name] = now_ms
                    self.last_state[name] = state
                    if state == 0:
                        events.append(name)
        return events
