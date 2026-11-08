"""MAX4466 analog microphone input and lightweight sound classifier.

The MAX4466 output is DC-biased around VCC/2, so every window's own centre is
measured and removed before computing the AC RMS level and the zero-crossing
rate (ZCR).

Events returned by sample():
    silence, sound_speech, sound_music, sound_noise

Event logic (so the face does not flicker):
  * a new sound class is accepted only after AUDIO_CONFIRM_WINDOWS windows in
    a row (a loud clap, sound_noise, is accepted immediately);
  * a short pause (shorter than AUDIO_SILENCE_HOLD_MS) does not count as
    silence;
  * while the same sound continues, its event is repeated every
    AUDIO_EVENT_HOLD_MS, so the emotion timer is refreshed;
  * mute_for() makes the microphone deaf while the speaker is playing.

This is a simple sound-reactive heuristic, not speech recognition. Thresholds
in config.py must be calibrated on the real microphone (calibrate_mic.py).
"""

import math
from array import array
from machine import ADC, Pin
import config

try:
    from time import ticks_diff, ticks_add, ticks_us, sleep_us
except ImportError:  # running the tests on a PC
    import time as _t

    def ticks_diff(a, b):
        return a - b

    def ticks_add(a, b):
        return a + b

    def ticks_us():
        return int(_t.monotonic() * 1000000)

    def sleep_us(us):
        _t.sleep(us / 1000000.0)


class AudioAnalyzer:
    EVENTS = ("silence", "sound_speech", "sound_music", "sound_noise")

    def __init__(self):
        self.adc = ADC(Pin(config.MIC_ADC_PIN))

        # 11 dB attenuation = widest input range (about 0..2.5 V usable).
        # Without it the MAX4466 signal (centre 1.65 V) would be clipped,
        # so a missing constant is an error, not something to skip.
        if not hasattr(ADC, "ATTN_11DB"):
            raise RuntimeError("ADC.ATTN_11DB not found: update MicroPython")
        self.adc.atten(ADC.ATTN_11DB)

        self.samples = array("H", [0] * config.MIC_SAMPLE_COUNT)
        self.current = "silence"      # sound class we are currently "in"
        self.pending = None           # candidate class waiting for confirmation
        self.pending_count = 0
        self.last_event_ms = 0
        self.last_sound_ms = 0
        self.muted_until = None

        self.last_rms = 0
        self.last_zcr = 0.0
        self.last_center = 2048
        self.last_window_us = 0

    # ------------------------------------------------------------- control
    def mute_for(self, now_ms, duration_ms):
        """Ignore the microphone for duration_ms (speaker is playing)."""
        self.muted_until = ticks_add(now_ms, duration_ms)
        self.pending = None
        self.pending_count = 0

    def _is_muted(self, now_ms):
        return (self.muted_until is not None
                and ticks_diff(now_ms, self.muted_until) < 0)

    # ------------------------------------------------------------ analysis
    def _read_samples(self):
        """Collect a short audio window, converted to 12-bit values."""
        delay_us = config.MIC_SAMPLE_PERIOD_US
        samples = self.samples
        read = self.adc.read_u16
        started = ticks_us()
        for i in range(len(samples)):
            samples[i] = read() >> 4
            if delay_us:
                sleep_us(delay_us)
        self.last_window_us = ticks_diff(ticks_us(), started)

    def _features(self):
        """Return AC RMS and zero-crossing rate after DC-offset removal."""
        count = len(self.samples)
        if count == 0:
            return 0, 0.0

        center = sum(self.samples) // count
        self.last_center = center

        total = 0
        crossings = 0
        previous_sign = 0
        for raw in self.samples:
            sample = raw - center
            total += sample * sample
            if sample > 0:
                sign = 1
            elif sample < 0:
                sign = -1
            else:
                sign = 0
            if sign and previous_sign and sign != previous_sign:
                crossings += 1
            if sign:
                previous_sign = sign

        rms = int(math.sqrt(total // count))
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

    # --------------------------------------------------------------- events
    def sample(self, now_ms):
        """Listen for one window. Returns an event name or None."""
        if self._is_muted(now_ms):
            return None

        self._read_samples()
        rms, zcr = self._features()
        raw = self._classify(rms, zcr)

        if raw != "silence":
            self.last_sound_ms = now_ms
        elif (self.current != "silence"
              and ticks_diff(now_ms, self.last_sound_ms) < config.AUDIO_SILENCE_HOLD_MS):
            raw = self.current        # short pause inside a sound: keep it

        if raw == self.current:
            self.pending = None
            self.pending_count = 0
            # Same sound goes on: repeat its event to refresh emotion timers.
            if (raw != "silence"
                    and ticks_diff(now_ms, self.last_event_ms) >= config.AUDIO_EVENT_HOLD_MS):
                self.last_event_ms = now_ms
                return raw
            return None

        # A different class: accept it after a few windows in a row
        # (a loud clap is accepted at once).
        need = 1 if raw == "sound_noise" else config.AUDIO_CONFIRM_WINDOWS
        if raw == self.pending:
            self.pending_count += 1
        else:
            self.pending = raw
            self.pending_count = 1
        if self.pending_count < need:
            return None

        self.pending = None
        self.pending_count = 0
        self.current = raw
        self.last_event_ms = now_ms
        return raw

    def status(self):
        return {
            "event": self.current,
            "rms": self.last_rms,
            "zcr": round(self.last_zcr, 3),
            "center": self.last_center,
            "window_us": self.last_window_us,
        }

    def deinit(self):
        self.adc = None

