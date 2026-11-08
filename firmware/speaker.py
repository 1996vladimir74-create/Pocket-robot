"""MAX98357A I2S amplifier output: beeps and short melodies.

The MAX98357A is a digital (I2S) class-D amplifier. It has no volume input,
so volume is applied in software by scaling the sample amplitude
(percent 0..100, perceptual curve: amplitude ~ volume squared).

Non-blocking: play()/play_sequence() only start a sound. Call update(now_ms)
every frame: it renders one note at a time and keeps the I2S buffer filled
about LEAD_MS ahead of real time, so the main loop is never blocked.

Stream layout: LEAD_IN_MS of silence (amplifier wake-up) + the notes + TAIL_MS
of silence. The amplifier's SD pin (config.AMP_SD) is high only while a sound
is playing.
"""

import math
from machine import I2S, Pin
import config

try:
    from time import ticks_diff, ticks_add
except ImportError:  # running the tests on a PC
    def ticks_diff(a, b):
        return a - b

    def ticks_add(a, b):
        return a + b


class Speaker:
    LEAD_IN_MS = 30       # silence before the first note (amplifier wake-up)
    TAIL_MS = 120         # silence after the last note
    LEAD_MS = 150         # keep the I2S buffer filled this far ahead of real time
    MAX_FEED_MS = 250     # never queue more than this in one update()
    FADE_MS = 6           # note fade in/out against clicks

    def __init__(self):
        self.rate = config.AUDIO_SAMPLE_RATE
        self.i2s = I2S(
            config.AMP_I2S_ID,
            sck=Pin(config.AMP_I2S_BCLK),
            ws=Pin(config.AMP_I2S_LRC),
            sd=Pin(config.AMP_I2S_DIN),
            mode=I2S.TX,
            bits=16,
            format=I2S.MONO,
            rate=self.rate,
            ibuf=config.AUDIO_I2S_IBUF,
        )
        sd_pin = getattr(config, "AMP_SD", None)
        self.sd = Pin(sd_pin, Pin.OUT, value=0) if sd_pin is not None else None

        self._table = [int(32767 * math.sin(2 * math.pi * i / 256)) for i in range(256)]
        self.volume = max(0, min(100, int(config.SPEAKER_VOLUME)))

        self.state = "idle"       # idle / stream / drain
        self.phase = "done"       # lead / notes / tail / done (what is rendered next)
        self.notes = []
        self.start_ms = 0
        self.fed = 0              # frames already given to I2S
        self.cur = None           # bytes of the segment being streamed
        self.cur_pos = 0

    # --------------------------------------------------------------- volume
    def set_volume(self, percent):
        self.volume = max(0, min(100, int(percent)))
        if self.volume == 0 and self.busy:
            self.stop()
        return self.volume

    def volume_up(self, step=None):
        return self.set_volume(self.volume + (step or getattr(config, "VOLUME_STEP", 5)))

    def volume_down(self, step=None):
        return self.set_volume(self.volume - (step or getattr(config, "VOLUME_STEP", 5)))

    def _amplitude(self):
        level = self.volume / 100.0
        return int(config.AUDIO_MAX_AMPLITUDE * level * level)

    # ------------------------------------------------------------- playback
    @property
    def busy(self):
        return self.state != "idle"

    @staticmethod
    def sequence_duration(notes):
        total = 0
        for _freq, duration in notes:
            total += duration
        return total

    @classmethod
    def playback_ms(cls, notes):
        """Total time the amplifier is active for these notes."""
        return cls.sequence_duration(notes) + cls.LEAD_IN_MS + cls.TAIL_MS

    def play(self, frequency=880, duration_ms=80, now_ms=0):
        self.play_sequence(((frequency, duration_ms),), now_ms)

    def play_sequence(self, notes, now_ms=0):
        """notes: sequence of (frequency_hz, duration_ms); frequency 0 = pause."""
        notes = [(f, d) for f, d in notes if d > 0]
        if not notes or self.volume <= 0:
            return
        start = now_ms
        if self.state != "idle":
            # Queue behind what is already in the I2S buffer (no overlap, no stall)
            remaining = self.fed * 1000 // self.rate - ticks_diff(now_ms, self.start_ms)
            if remaining > 0:
                start = ticks_add(now_ms, remaining)
        self.notes = notes
        self.phase = "lead"
        self.cur = None
        self.cur_pos = 0
        self.fed = 0
        self.start_ms = start
        self.state = "stream"
        if self.sd is not None:
            self.sd.value(1)

    def update(self, now_ms):
        if self.state == "idle":
            return

        if self.state == "stream":
            elapsed = ticks_diff(now_ms, self.start_ms)
            target = (elapsed + self.LEAD_MS) * self.rate // 1000
            cap = self.fed + self.rate * self.MAX_FEED_MS // 1000
            if target > cap:
                target = cap
            while self.fed < target:
                if self.cur is None or self.cur_pos >= len(self.cur):
                    self.cur = self._next_segment()
                    self.cur_pos = 0
                    if self.cur is None:
                        self.state = "drain"
                        break
                frames = min(target - self.fed, (len(self.cur) - self.cur_pos) // 2)
                if frames <= 0:
                    break
                end = self.cur_pos + frames * 2
                self.i2s.write(memoryview(self.cur)[self.cur_pos:end])
                self.cur_pos = end
                self.fed += frames

        if self.state == "drain" and ticks_diff(now_ms, self.start_ms) >= self.fed * 1000 // self.rate:
            self._finish()

    def stop(self):
        was_streaming = self.fed > 0
        self.state = "idle"
        self.phase = "done"
        self.notes = []
        self.cur = None
        self.cur_pos = 0
        self.fed = 0
        if self.sd is not None:
            self.sd.value(0)
        if was_streaming:
            # leave silence at the end of the I2S buffer, not the tail of a tone
            self.i2s.write(bytes(self.rate * self.TAIL_MS // 1000 * 2))

    def deinit(self):
        self.stop()
        self.i2s.deinit()

    # ------------------------------------------------------------ internals
    def _finish(self):
        self.state = "idle"
        self.cur = None
        self.fed = 0
        if self.sd is not None:
            self.sd.value(0)

    def _next_segment(self):
        if self.phase == "lead":
            self.phase = "notes"
            return bytearray(self.rate * self.LEAD_IN_MS // 1000 * 2)
        if self.phase == "notes":
            while self.notes:
                frequency, duration = self.notes.pop(0)
                segment = self._render_note(int(frequency), int(duration))
                if len(segment):
                    return segment
            self.phase = "done"
            return bytearray(self.rate * self.TAIL_MS // 1000 * 2)
        return None

    def _render_note(self, frequency, duration_ms):
        """16-bit mono little-endian samples of one note (or silence)."""
        frames = self.rate * duration_ms // 1000
        buf = bytearray(frames * 2)
        amp = self._amplitude()
        if frequency <= 0 or amp <= 0 or frames <= 0:
            return buf

        scaled = [t * amp // 32767 for t in self._table]
        low = bytes([v & 255 for v in scaled])
        high = bytes([(v >> 8) & 255 for v in scaled])
        step = int(frequency * 256 * 65536 / self.rate)   # phase step, 16 fractional bits
        mask = (256 << 16) - 1
        fade = min(frames // 2, self.rate * self.FADE_MS // 1000)

        phase = 0
        for i in range(frames):
            index = phase >> 16
            j = i * 2
            if i < fade or i >= frames - fade:
                k = i if i < fade else frames - 1 - i
                v = scaled[index] * k // fade
                buf[j] = v & 255
                buf[j + 1] = (v >> 8) & 255
            else:
                buf[j] = low[index]
                buf[j + 1] = high[index]
            phase = (phase + step) & mask
        return buf
