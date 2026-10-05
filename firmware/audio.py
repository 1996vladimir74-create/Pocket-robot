"""INMP441 input and simple local sound-event classifier.

V1 intentionally uses lightweight signal features only. It can reliably
react to silence and loud sounds, and uses zero-crossing rate as a rough
speech/noise/music hint. It is NOT speech recognition and should be
calibrated on the real microphone before treating music classification as
accurate.
"""

from array import array
from machine import I2S, Pin
import config


class AudioAnalyzer:
    EVENTS = ("silence", "sound_speech", "sound_music", "sound_noise")

    def __init__(self):
        self.i2s = I2S(
            config.MIC_I2S_ID,
            sck=Pin(config.MIC_BCLK),
            ws=Pin(config.MIC_WS),
            sd=Pin(config.MIC_SD),
            mode=I2S.RX,
            bits=config.MIC_SAMPLE_BITS,
            format=I2S.MONO,
            rate=config.MIC_SAMPLE_RATE,
            ibuf=config.MIC_BUFFER_SAMPLES * 8,
        )
        self.samples = array("i", [0] * config.MIC_BUFFER_SAMPLES)
        self.last_event = "silence"
        self.last_event_ms = 0
        self.last_rms = 0
        self.last_zcr = 0.0

    def _features(self):
        total = 0
        crossings = 0
        previous = 0
        count = len(self.samples)

        # INMP441/ESP32 I2S commonly presents 24-bit audio in 32-bit words.
        # Scale down so thresholds stay in a manageable integer range.
        for raw in self.samples:
            sample = raw >> 8
            total += sample * sample
            sign = 1 if sample >= 0 else -1
            if previous and sign != previous:
                crossings += 1
            previous = sign

        mean_square = total // max(1, count)
        rms = int(mean_square ** 0.5)
        zcr = float(crossings) / max(1, count - 1)
        self.last_rms = rms
        self.last_zcr = zcr
        return rms, zcr

    def _classify(self, rms, zcr):
        if rms < config.AUDIO_SILENCE_RMS:
            return "silence"
        if rms >= config.AUDIO_LOUD_RMS:
            return "sound_noise"
        if config.AUDIO_SPEECH_ZCR_MIN <= zcr <= config.AUDIO_SPEECH_ZCR_MAX:
            return "sound_speech"
        return "sound_music"

    def sample(self, now_ms):
        read_bytes = self.i2s.readinto(self.samples)
        if not read_bytes:
            return None

        rms, zcr = self._features()
        event = self._classify(rms, zcr)

        # Prevent rapid event flapping when the signal sits near a threshold.
        if event != self.last_event:
            if now_ms - self.last_event_ms < 150:
                return None
            self.last_event = event
            self.last_event_ms = now_ms
            return event

        return None

    def status(self):
        return {
            "event": self.last_event,
            "rms": self.last_rms,
            "zcr": self.last_zcr,
        }

    def deinit(self):
        self.i2s.deinit()
