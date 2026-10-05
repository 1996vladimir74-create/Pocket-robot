"""Minimal ST7789V3 driver for the 240x280 SPI display.

The driver consumes the drawing-command dictionaries produced by face.py.
It intentionally uses only MicroPython standard modules.
"""

import math
from machine import Pin, SPI
import config


class ST7789:
    SWRESET = 0x01
    SLPOUT = 0x11
    COLMOD = 0x3A
    MADCTL = 0x36
    INVON = 0x21
    INVOFF = 0x20
    CASET = 0x2A
    RASET = 0x2B
    RAMWR = 0x2C
    NORON = 0x13
    DISPON = 0x29

    def __init__(self):
        self.width = config.DISPLAY_WIDTH
        self.height = config.DISPLAY_HEIGHT
        self.x_offset = config.DISPLAY_X_OFFSET
        self.y_offset = config.DISPLAY_Y_OFFSET

        self.spi = SPI(
            config.DISPLAY_SPI_ID,
            baudrate=40000000,
            polarity=0,
            phase=0,
            sck=Pin(config.DISPLAY_SCK),
            mosi=Pin(config.DISPLAY_MOSI),
        )
        self.cs = Pin(config.DISPLAY_CS, Pin.OUT, value=1)
        self.dc = Pin(config.DISPLAY_DC, Pin.OUT, value=0)
        self.rst = Pin(config.DISPLAY_RST, Pin.OUT, value=1)
        self.bl = Pin(config.DISPLAY_BL, Pin.OUT, value=0)
        self.buffer = bytearray(self.width * self.height * 2)
        self._init_display()

    def _select(self):
        self.cs.value(0)

    def _deselect(self):
        self.cs.value(1)

    def _write_cmd(self, cmd):
        self._select()
        self.dc.value(0)
        self.spi.write(bytes((cmd,)))
        self._deselect()

    def _write_data(self, data):
        self._select()
        self.dc.value(1)
        self.spi.write(data)
        self._deselect()

    def _init_display(self):
        import time
        self.rst.value(0)
        time.sleep_ms(20)
        self.rst.value(1)
        time.sleep_ms(120)

        self._write_cmd(self.SWRESET)
        time.sleep_ms(120)
        self._write_cmd(self.SLPOUT)
        time.sleep_ms(120)

        self._write_cmd(self.COLMOD)
        self._write_data(b"\x55")  # RGB565

        self._write_cmd(self.MADCTL)
        self._write_data(b"\x00")

        self._write_cmd(self.INVON if config.DISPLAY_INVERT else self.INVOFF)
        self._write_cmd(self.NORON)
        self._write_cmd(self.DISPON)
        time.sleep_ms(100)
        self.bl.value(1)
        self.clear(0x0000)

    def _set_window(self, x0, y0, x1, y1):
        x0 += self.x_offset
        x1 += self.x_offset
        y0 += self.y_offset
        y1 += self.y_offset
        self._write_cmd(self.CASET)
        self._write_data(bytes((x0 >> 8, x0 & 255, x1 >> 8, x1 & 255)))
        self._write_cmd(self.RASET)
        self._write_data(bytes((y0 >> 8, y0 & 255, y1 >> 8, y1 & 255)))
        self._write_cmd(self.RAMWR)

    @staticmethod
    def _rgb565(color):
        return color & 0xFFFF

    def clear(self, color=0):
        hi = (color >> 8) & 255
        lo = color & 255
        self.buffer[:] = bytes((hi, lo)) * (self.width * self.height)

    def _pixel(self, x, y, color):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        i = (y * self.width + x) * 2
        self.buffer[i] = (color >> 8) & 255
        self.buffer[i + 1] = color & 255

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(self.width, int(x + w))
        y1 = min(self.height, int(y + h))
        for yy in range(y0, y1):
            base = (yy * self.width + x0) * 2
            row = bytearray((color >> 8, color & 255)) * (x1 - x0)
            self.buffer[base:base + len(row)] = row

    def line(self, x0, y0, x1, y1, color, thickness=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        radius = max(0, int(thickness // 2))
        while True:
            for ox in range(-radius, radius + 1):
                for oy in range(-radius, radius + 1):
                    self._pixel(x0 + ox, y0 + oy, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ellipse(self, x, y, w, h, color, fill=False):
        cx = x + w / 2.0
        cy = y + h / 2.0
        rx = max(1.0, w / 2.0)
        ry = max(1.0, h / 2.0)
        if fill:
            for yy in range(int(y), int(y + h) + 1):
                dy = (yy - cy) / ry
                if abs(dy) <= 1:
                    span = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
                    self.line(int(cx - span), yy, int(cx + span), yy, color, 1)
        else:
            steps = max(24, int(2 * math.pi * max(rx, ry)))
            last_x = None
            last_y = None
            for i in range(steps + 1):
                a = 2 * math.pi * i / steps
                px = int(cx + rx * math.cos(a))
                py = int(cy + ry * math.sin(a))
                if last_x is not None:
                    self.line(last_x, last_y, px, py, color, 1)
                last_x, last_y = px, py

    def arc(self, x, y, w, h, start, end, color, thickness=1):
        cx = x + w / 2.0
        cy = y + h / 2.0
        rx = max(1.0, w / 2.0)
        ry = max(1.0, h / 2.0)
        span = max(1, int(abs(end - start)))
        steps = max(12, span * 2)
        last_x = None
        last_y = None
        for i in range(steps + 1):
            a = math.radians(start + (end - start) * i / steps)
            px = int(cx + rx * math.cos(a))
            py = int(cy + ry * math.sin(a))
            if last_x is not None:
                self.line(last_x, last_y, px, py, color, thickness)
            last_x, last_y = px, py

    def draw_command(self, command):
        kind = command["type"]
        if kind == "fill_rect":
            self.fill_rect(command["x"], command["y"], command["width"], command["height"], command["color"])
        elif kind == "fill_ellipse":
            self.ellipse(command["x"], command["y"], command["width"], command["height"], command["color"], True)
        elif kind == "ellipse":
            self.ellipse(command["x"], command["y"], command["width"], command["height"], command["color"], False)
        elif kind == "line":
            self.line(command["x1"], command["y1"], command["x2"], command["y2"], command["color"], command.get("thickness", 1))
        elif kind == "arc":
            self.arc(command["x"], command["y"], command["width"], command["height"], command["start"], command["end"], command["color"], command.get("thickness", 1))

    def render(self, commands):
        self.clear(config.DISPLAY_INVERT and 0x0000 or 0x0000)
        for command in commands:
            self.draw_command(command)
        self._set_window(0, 0, self.width - 1, self.height - 1)
        self._select()
        self.dc.value(1)
        self.spi.write(self.buffer)
        self._deselect()
