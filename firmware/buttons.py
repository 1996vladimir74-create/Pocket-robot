"""Three debounced active-low buttons with long-press support.

poll() returns a list of event names:
  "action"                         ACTION pressed (immediately)
  "mode" / "back"                  short press, reported when the button is released
  "mode_hold" / "back_hold"        long press: first after VOLUME_LONG_PRESS_MS, then
                                   repeated every VOLUME_REPEAT_MS while still held
The two buttons that have a long-press function are VOLUME_UP_BUTTON and
VOLUME_DOWN_BUTTON from config.py. After a long press no short-press event is
sent when the button is released.
"""

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
        self.hold_buttons = (config.VOLUME_UP_BUTTON, config.VOLUME_DOWN_BUTTON)
        self.last_state = {name: 1 for name in self.pins}
        self.last_change = {name: 0 for name in self.pins}
        self.pressed_at = {name: None for name in self.pins}
        self.held = {name: False for name in self.pins}
        self.next_repeat = {name: 0 for name in self.pins}

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
                    if state == 0:                              # pressed
                        self.pressed_at[name] = now_ms
                        self.held[name] = False
                        if name not in self.hold_buttons:
                            events.append(name)
                    else:                                       # released
                        if (name in self.hold_buttons
                                and self.pressed_at[name] is not None
                                and not self.held[name]):
                            events.append(name)                 # short press
                        self.pressed_at[name] = None
                        self.held[name] = False
            elif (state == 0 and name in self.hold_buttons
                  and self.pressed_at[name] is not None):
                # still pressed: long press and auto-repeat
                if not self.held[name]:
                    if time.ticks_diff(now_ms, self.pressed_at[name]) >= config.VOLUME_LONG_PRESS_MS:
                        self.held[name] = True
                        self.next_repeat[name] = time.ticks_add(now_ms, config.VOLUME_REPEAT_MS)
                        events.append(name + "_hold")
                elif time.ticks_diff(now_ms, self.next_repeat[name]) >= 0:
                    self.next_repeat[name] = time.ticks_add(now_ms, config.VOLUME_REPEAT_MS)
                    events.append(name + "_hold")
        return events
