"""Bring-up step 1: test the display alone.  On the board:  import test_display

What you should see: a white 1-pixel frame exactly on the screen edge,
red / green / blue / white bars (in that order, top to bottom) and text.
 * frame cut off or a noisy strip at an edge -> change DISPLAY_Y_OFFSET / X_OFFSET
 * red and blue swapped                       -> DISPLAY_MADCTL = 0x08
 * colours look like a negative               -> toggle DISPLAY_INVERT
 * blank screen                               -> try DISPLAY_SPI_ID = 2, lower DISPLAY_SPI_BAUD
"""

import time
import config
from display import ST7789

d = ST7789()
w, h = d.width, d.height

d.clear(0x0000)
bars = ((0xF800, "RED"), (0x07E0, "GREEN"), (0x001F, "BLUE"), (0xFFFF, "WHITE"))
bar_h = (h - 40) // len(bars)
for i, (color, name) in enumerate(bars):
    y = 20 + i * bar_h
    d.fill_rect(10, y, w - 20, bar_h - 4, color)
    d.fb.text(name, 20, y + bar_h // 2 - 4, d._c(0x0000))

white = d._c(0xFFFF)
d.fb.rect(0, 0, w, h, white)           # edge frame
d.fb.text("TOP", w // 2 - 12, 6, white)
d.fb.text("BOTTOM", w // 2 - 24, h - 14, white)
d._flush(0, h - 1)
print("Sent", d.last_bytes, "bytes. Check the picture, see the notes in this file.")

t = time.ticks_ms()
for _ in range(10):
    d._flush(0, h - 1)
ms = time.ticks_diff(time.ticks_ms(), t) // 10
print("Full-frame SPI transfer: {} ms (baud {})".format(ms, config.DISPLAY_SPI_BAUD))
