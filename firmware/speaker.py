"""PAM8403 analog amplifier output using ESP32-S3 PWM.

The PAM8403 accepts an analog input. For V1 we use the ESP32-S3 PWM output
as a simple square-wave tone source. This is suitable for notification
beeps and simple tones; it is not a high-fidelity audio playback path.
"""

from machine import PWM, Pin
import config


class Speaker:
    def __init__(self):
        self.pwm = None
        self.volume = 0.20

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))

    def tone(self, frequency=880, duration_ms=80):
        if frequency <= 0 or duration_ms <= 0:
            return

        self.pwm = PWM(
            Pin(config.AMP_AUDIO_OUT),
            freq=int(frequency),
            duty_u16=32768,
        )
        try:
            # A square-wave tone is sufficient for V1 notification sounds.
            # The PAM8403 provides the power amplification to the speakers.
            import time
            time.sleep_ms(int(duration_ms))
        finally:
            self.pwm.duty_u16(0)
            self.pwm.deinit()
            self.pwm = None

    def deinit(self):
        if self.pwm is not None:
            self.pwm.duty_u16(0)
            self.pwm.deinit()
            self.pwm = None
