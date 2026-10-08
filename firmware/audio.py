"""MAX4466 analog microphone input and lightweight sound classifier.

V1 uses the MAX4466 microphone amplifier connected directly to an ADC1 pin.
The MAX4466 output is DC-biased around VCC/2, so the analyzer removes the
measured DC offset before calculating RMS and zero-crossing rate.

This is intentionally a simple sound-reactive classifier, not speech
recognition. Thresholds must be calibrated on the real microphone because
the MAX4466 module has adjustable gain.
"""

import math
import time
from machine import ADC, Pin
import config


class AudioAnalyzer:
    EVENTS = ("silence", "sound_speech", "sound_music", "sound_noise")

    def __init__(self):
        self.adc = ADC(Pin(config.MIC_ADC_PIN))

        # ESP32-S3 ADC attenuation. 11 dB gives the widest useful input range
        # for a MAX4466 powered from 3.3 V. The microphone must also be powered
        # from 3.3 V so its output cannot exceed the ESP32 input supply.
        if hasattr(ADC, "ATTN_11DB"):
            self.adc.atten(ADC.ATTN_11DB)
        elif hasattr(ADC, "ATTN_11DB"):
            self.adc.atten(ADC.ATTN_11DB)

        self.samples = [0] * config.MIC_SAMPLE_COUNT
        self.last_event = "silence"
        self.last_event_ms = 0
        self.last_rms = 0
        self.last_zcr = 0.0
        self.last_center = 2048

    def _read_samples(self):
        """Collect a short audio window and convert ADC readings to 12-bit."""
        delay_us = config.MIC_SAMPLE_PERIOD_US
        for i in range(len(self.samples)):
            # read_u16 is the portable MicroPython ADC API; normalize to the
            # nominal 12-bit ADC scale for stable, readable thresholds.
            self.samples[i] = self.adc.read_u16() >> 4
            if delay_us:
                time.sleep_us(delay_us)

    def _features(self):
        """Return AC RMS and zero-crossing rate after DC-offset removal."""
        count = len(self.samples)
        if count == 0:
            return 0, 0.0

        # MAX4466 output is centered near VCC/2. Measure the actual center for
        # every window instead of assuming the ADC midpoint is exactly 2048.
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

        mean_square = total // max(1, count)
        rms = int(math.sqrt(mean_square))
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
        self._read_samples()
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
            "center": self.last_center,
        }

    def deinit(self):
        # ADC does not require an explicit deinit on MicroPython ESP32.
        self.adc = None
