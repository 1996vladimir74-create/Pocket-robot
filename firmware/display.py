"""ST7789V3 driver for the 240x280 SPI display, built on framebuf.

All pixels are drawn by MicroPython's native framebuf (C speed). Only the
rows that changed since the previous frame are sent over SPI.

It consumes the drawing-command dictionaries produced by face.py.
NOTE: the 134 KB frame buffer needs PSRAM: flash a MicroPython build for
ESP32_GENERIC_S3 with SPIRAM_OCT (N16R8 module).
"""

import math
import time
import framebuf
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
        self.partial = getattr(config, "DISPLAY_PARTIAL", True)

        self.spi = SPI(
            config.DISPLAY_SPI_ID,
            baudrate=config.DISPLAY_SPI_BAUD,
            polarity=0,
            phase=0,
            sck=Pin(config.DISPLAY_SCK),
            mosi=Pin(config.DISPLAY_MOSI),
        )
        self.cs = Pin(config.DISPLAY_CS, Pin.OUT, value=1)
        self.dc = Pin(config.DISPLAY_DC, Pin.OUT, value=0)
        self.rst = Pin(config.DISPLAY_RST, Pin.OUT, value=1)
        self.bl = Pin(config.DISPLAY_BL, Pin.OUT, value=0)

        # Allocated once: no per-frame memory churn.
        self._cmd = bytearray(1)
        self._win = bytearray(4)
        try:
            self.buffer = bytearray(self.width * self.height * 2)
        except MemoryError:
            raise RuntimeError(
                "Not enough RAM for the frame buffer: flash a MicroPython "
                "build with PSRAM (ESP32_GENERIC_S3, SPIRAM_OCT)")
        self._view = memoryview(self.buffer)
        self.fb = framebuf.FrameBuffer(
            self.buffer, self.width, self.height, framebuf.RGB565)
        self._native_ellipse = hasattr(self.fb, "ellipse")

        self._bg = 0          # background colour of the last frame
        self._prev = None     # (top, bottom) rows used by the last frame
        self.last_bytes = 0   # bytes sent by the last flush (diagnostics)
        self._init_display()

    # ------------------------------------------------------------ low level
    def _write_cmd(self, cmd):
        self._cmd[0] = cmd
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(self._cmd)
        self.cs.value(1)

    def _write_data(self, data):
        self.cs.value(0)
        self.dc.value(1)
        self.spi.write(data)
        self.cs.value(1)

    def _init_display(self):
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
        self._write_data(bytes((config.DISPLAY_MADCTL & 0xFF,)))

        self._write_cmd(self.INVON if config.DISPLAY_INVERT else self.INVOFF)
        self._write_cmd(self.NORON)
        self._write_cmd(self.DISPON)
        time.sleep_ms(100)

        # Send one black frame first, only then switch the backlight on,
        # otherwise the random RAM content flashes ("snow").
        self.fb.fill(0)
        self._flush(0, self.height - 1)
        self.bl.value(1)

    def _set_window(self, x0, y0, x1, y1):
        x0 += self.x_offset
        x1 += self.x_offset
        y0 += self.y_offset
        y1 += self.y_offset
        w = self._win
        self._write_cmd(self.CASET)
        w[0] = x0 >> 8
        w[1] = x0 & 255
        w[2] = x1 >> 8
        w[3] = x1 & 255
        self._write_data(w)
        self._write_cmd(self.RASET)
        w[0] = y0 >> 8
        w[1] = y0 & 255
        w[2] = y1 >> 8
        w[3] = y1 & 255
        self._write_data(w)
        self._write_cmd(self.RAMWR)

    def _flush(self, top, bottom):
        """Send full-width rows top..bottom (inclusive) to the display."""
        row = self.width * 2
        self._set_window(0, top, self.width - 1, bottom)
        self.cs.value(0)
        self.dc.value(1)
        self.spi.write(self._view[top * row:(bottom + 1) * row])
        self.cs.value(1)
        self.last_bytes = (bottom - top + 1) * row

    # --------------------------------------------------------------- drawing
    @staticmethod
    def _c(color):
        # framebuf stores RGB565 low byte first, the ST7789 wants the high
        # byte first, so swap the two bytes of every colour.
        color &= 0xFFFF
        return ((color & 0xFF) << 8) | (color >> 8)

    def clear(self, color=0):
        self.fb.fill(self._c(color))

    def fill_rect(self, x, y, w, h, color):
        self.fb.fill_rect(int(x), int(y), int(w), int(h), self._c(color))

    def line(self, x0, y0, x1, y1, color, thickness=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        c = self._c(color)
        r = max(0, int(thickness) // 2)
        if r == 0:
            self.fb.line(x0, y0, x1, y1, c)
            return
        steep = abs(y1 - y0) > abs(x1 - x0)
        for o in range(-r, r + 1):
            if steep:
                self.fb.line(x0 + o, y0, x1 + o, y1, c)
            else:
                self.fb.line(x0, y0 + o, x1, y1 + o, c)

    def ellipse(self, x, y, w, h, color, fill=False):
        rx = max(1, int(w) // 2)
        ry = max(1, int(h) // 2)
        cx = int(x) + rx
        cy = int(y) + ry
        c = self._c(color)
        if self._native_ellipse:
            self.fb.ellipse(cx, cy, rx, ry, c, fill)
        elif fill:
            for dy in range(-ry, ry + 1):
                k = 1.0 - (dy / ry) * (dy / ry)
                span = int(rx * math.sqrt(k if k > 0 else 0))
                self.fb.fill_rect(cx - span, cy + dy, 2 * span + 1, 1, c)
        else:
            last = None
            for i in range(37):
                a = i * math.pi / 18
                p = (int(cx + rx * math.cos(a)), int(cy + ry * math.sin(a)))
                if last:
                    self.fb.line(last[0], last[1], p[0], p[1], c)
                last = p

    def arc(self, x, y, w, h, start, end, color, thickness=1):
        cx = x + w / 2.0
        cy = y + h / 2.0
        rx = max(1.0, w / 2.0)
        ry = max(1.0, h / 2.0)
        steps = max(6, int(abs(end - start)) // 8)
        last = None
        for i in range(steps + 1):
            a = math.radians(start + (end - start) * i / steps)
            p = (int(cx + rx * math.cos(a)), int(cy + ry * math.sin(a)))
            if last is not None:
                self.line(last[0], last[1], p[0], p[1], color, thickness)
            last = p

    def draw_command(self, command):
        kind = command["type"]
        if kind == "fill_rect":
            self.fill_rect(command["x"], command["y"], command["width"],
                           command["height"], command["color"])
        elif kind == "fill_ellipse":
            self.ellipse(command["x"], command["y"], command["width"],
                         command["height"], command["color"], True)
        elif kind == "ellipse":
            self.ellipse(command["x"], command["y"], command["width"],
                         command["height"], command["color"], False)
        elif kind == "line":
            self.line(command["x1"], command["y1"], command["x2"],
                      command["y2"], command["color"],
                      command.get("thickness", 1))
        elif kind == "arc":
            self.arc(command["x"], command["y"], command["width"],
                     command["height"], command["start"], command["end"],
                     command["color"], command.get("thickness", 1))

    # ------------------------------------------------------------- rendering
    def _scan(self, commands):
        """Return (background_colour, top_row, bottom_row) of a frame.

        A full-screen fill_rect is the background: it is not counted as
        content (it is replaced by clearing only the changed rows).
        top > bottom means that the frame draws nothing.
        """
        bg = 0
        top = self.height
        bottom = -1
        for c in commands:
            kind = c["type"]
            if kind == "line":
                t = c.get("thickness", 1) // 2 + 3
                y0 = min(c["y1"], c["y2"]) - t
                y1 = max(c["y1"], c["y2"]) + t
            else:
                if (kind == "fill_rect" and c["x"] <= 0 and c["y"] <= 0
                        and c["width"] >= self.width
                        and c["height"] >= self.height):
                    bg = c["color"]
                    continue
                t = c.get("thickness", 1) // 2 + 3 if kind == "arc" else 3
                y0 = c["y"] - t
                y1 = c["y"] + c["height"] + t
            if int(y0) < top:
                top = int(y0)
            if int(y1) > bottom:
                bottom = int(y1)
        if top < 0:
            top = 0
        if bottom > self.height - 1:
            bottom = self.height - 1
        return bg, top, bottom

    def render(self, commands):
        bg, top, bottom = self._scan(commands)

        if not self.partial or bg != self._bg:
            a, b = 0, self.height - 1
        else:
            a, b = top, bottom
            if self._prev is not None:
                if self._prev[0] < a:
                    a = self._prev[0]
                if self._prev[1] > b:
                    b = self._prev[1]
            if a > b:               # nothing drawn now, nothing to erase
                self._prev = None
                return

        self.fb.fill_rect(0, a, self.width, b - a + 1, self._c(bg))
        for command in commands:
            if (command["type"] == "fill_rect" and command["x"] <= 0
                    and command["y"] <= 0
                    and command["width"] >= self.width
                    and command["height"] >= self.height):
                continue            # background already painted above
            self.draw_command(command)
        self._flush(a, b)

        self._prev = (top, bottom) if top <= bottom else None
        self._bg = bg

