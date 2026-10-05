"""MAX98357A I2S speaker output."""

from array import array
from machine import I2S, Pin
import math
import config


class Speaker:
    def __init__(self):
        self.i2s = I2S(
            config.AMP_I2S_ID,
            sck=Pin(config.AMP_BCLK),
            ws=Pin(config.AMP_WS),
            sd=Pin(config.AMP_DIN),
            mode=I2S.TX,
            bits=16,
            format=I2S.MONO,
            rate=config.AMP_SAMPLE_RATE,
            ibuf=16000,
        )
        self.volume = 0.20
        self._tone_buffer = None

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))

    def tone(self, frequency=880, duration_ms=80):
        samples = max(1, int(config.AMP_SAMPLE_RATE * duration_ms / 1000))
        self._tone_buffer = array("h", [0] * samples)
        amplitude = int(12000 * self.volume)
        for i in range(samples):
            envelope = 1.0
            edge = min(i, samples - i - 1)
            fade = max(1, int(config.AMP_SAMPLE_RATE * 0.005))
            if edge < fade:
                envelope = edge / float(fade)
            self._tone_buffer[i] = int(amplitude * envelope * math.sin(2 * math.pi * frequency * i / config.AMP_SAMPLE_RATE))
        self.i2s.write(self._tone_buffer)
        self._tone_buffer = None

    def deinit(self):
        self.i2s.deinit()
