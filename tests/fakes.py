"""PC stand-ins for MicroPython hardware modules (machine, framebuf, time).

install() lets the firmware modules run in normal Python so their logic can
be unit-tested without the board.
"""

import sys
import time
import types

_t0 = time.monotonic()


def install_time():
    if not hasattr(time, "ticks_ms"):
        time.ticks_ms = lambda: int((time.monotonic() - _t0) * 1000)
        time.ticks_us = lambda: int((time.monotonic() - _t0) * 1000000)
        time.ticks_diff = lambda a, b: a - b
        time.ticks_add = lambda a, b: a + b
        time.sleep_ms = lambda ms: time.sleep(ms / 1000.0)
        time.sleep_us = lambda us: time.sleep(us / 1000000.0)


class Pin:
    IN, OUT, PULL_UP = 0, 1, 2
    levels = {}

    def __init__(self, n, mode=None, pull=None, value=None):
        self.n = n
        if value is not None:
            Pin.levels[n] = value
        Pin.levels.setdefault(n, 1)

    def value(self, v=None):
        if v is None:
            return Pin.levels[self.n]
        Pin.levels[self.n] = v


class ADC:
    ATTN_11DB = 3
    source = None          # test sets a callable returning a 12-bit value

    def __init__(self, pin):
        pass

    def atten(self, a):
        pass

    def read_u16(self):
        value = ADC.source() if ADC.source else 2048
        return int(value) << 4


class I2S:
    TX, RX = 0, 1
    MONO, STEREO = 0, 1
    instances = []

    def __init__(self, id, **kwargs):
        self.id = id
        self.kwargs = kwargs
        self.writes = []
        self.deinited = False
        I2S.instances.append(self)

    def write(self, data):
        chunk = bytes(data)
        self.writes.append(chunk)
        return len(chunk)

    def stream(self):
        return b"".join(self.writes)

    def deinit(self):
        self.deinited = True


class PWM:
    instances = []

    def __init__(self, pin, freq=0, duty_u16=0):
        self.freq_value = freq
        self.duty = duty_u16
        self.history = [(freq, duty_u16)]
        self.deinited = False
        PWM.instances.append(self)

    def freq(self, f):
        self.freq_value = f
        self.history.append((f, self.duty))

    def duty_u16(self, d):
        self.duty = d
        self.history.append((self.freq_value, d))

    def deinit(self):
        self.deinited = True


class SPI:
    """Emulates just enough of an ST7789 to rebuild the screen contents."""

    def __init__(self, *a, **k):
        import config
        self.cfg = config
        self.w = config.DISPLAY_WIDTH
        self.h = config.DISPLAY_HEIGHT
        self.screen = bytearray(self.w * self.h * 2)
        self.cmd = None
        self.col = (0, 0)
        self.row = (0, 0)
        self.sent = 0

    def write(self, data):
        d = bytes(data)
        self.sent += len(d)
        if Pin.levels.get(self.cfg.DISPLAY_DC) == 0:
            self.cmd = d[0]
            return
        if self.cmd == 0x2A:
            self.col = ((d[0] << 8) | d[1], (d[2] << 8) | d[3])
        elif self.cmd == 0x2B:
            self.row = ((d[0] << 8) | d[1], (d[2] << 8) | d[3])
        elif self.cmd == 0x2C:
            x0 = self.col[0] - self.cfg.DISPLAY_X_OFFSET
            y0 = self.row[0] - self.cfg.DISPLAY_Y_OFFSET
            assert self.col[1] - self.col[0] + 1 == self.w, "partial-width window"
            start = (y0 * self.w + x0) * 2
            self.screen[start:start + len(d)] = d


class FrameBuffer:
    """RGB565, little-endian pixels, like MicroPython's framebuf."""

    def __init__(self, buf, w, h, fmt):
        self.buf, self.w, self.h = buf, w, h

    def _px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 2
            self.buf[i] = c & 255
            self.buf[i + 1] = (c >> 8) & 255

    def fill(self, c):
        self.buf[:] = bytes((c & 255, (c >> 8) & 255)) * (self.w * self.h)

    def fill_rect(self, x, y, w, h, c):
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                self._px(xx, yy, c)

    def rect(self, x, y, w, h, c):
        self.line(x, y, x + w - 1, y, c)
        self.line(x, y + h - 1, x + w - 1, y + h - 1, c)
        self.line(x, y, x, y + h - 1, c)
        self.line(x + w - 1, y, x + w - 1, y + h - 1, c)

    def text(self, s, x, y, c):
        pass

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self._px(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ellipse(self, cx, cy, rx, ry, c, f=False, m=0xF):
        import math
        if f:
            for dy in range(-ry, ry + 1):
                span = int(rx * math.sqrt(max(0.0, 1.0 - (dy / ry) ** 2)))
                self.fill_rect(cx - span, cy + dy, 2 * span + 1, 1, c)
        else:
            for i in range(0, 360, 2):
                a = math.radians(i)
                self._px(int(cx + rx * math.cos(a)), int(cy + ry * math.sin(a)), c)


def install():
    """Register the fake modules. Safe to call repeatedly."""
    install_time()
    machine = types.ModuleType("machine")
    machine.Pin, machine.ADC, machine.SPI, machine.PWM = Pin, ADC, SPI, PWM
    machine.I2S = I2S
    sys.modules["machine"] = machine

    framebuf = types.ModuleType("framebuf")
    framebuf.FrameBuffer = FrameBuffer
    framebuf.RGB565 = 1
    sys.modules["framebuf"] = framebuf

    network = types.ModuleType("network")

    class WLAN:
        def __init__(self, i):
            pass

        def active(self, x):
            pass

        def isconnected(self):
            return False

        def connect(self, *a):
            pass

        def ifconfig(self):
            return ("0.0.0.0",)

    network.STA_IF = 0
    network.WLAN = WLAN
    sys.modules["network"] = network
