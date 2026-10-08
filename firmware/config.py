"""Hardware configuration for Pocket Robot V1.

Pin numbers are the current planned wiring for ESP32-S3-DevKitC-1 N16R8.
The V1 prototype currently uses an analog MAX4466 microphone and PAM8403
amplifier. The microphone can later be replaced by an INMP441 without
changing the higher-level emotion architecture.
"""

DEVICE_NAME = "PocketRobot"

# Display: 1.69 inch ST7789V3, 240x280, SPI
DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 280
DISPLAY_SPI_ID = 2
DISPLAY_SCK = 12
DISPLAY_MOSI = 11
DISPLAY_CS = 10
DISPLAY_DC = 9
DISPLAY_RST = 8
DISPLAY_BL = 7
DISPLAY_ROTATION = 0
DISPLAY_X_OFFSET = 0
DISPLAY_Y_OFFSET = 0
DISPLAY_INVERT = True

# Analog microphone: MAX4466 -> ESP32-S3 ADC1.
# GPIO1 is ADC1_CH0 and does not have the ESP32-S3 ADC2/Wi-Fi conflict.
MIC_ADC_PIN = 1
MIC_ADC_ATTEN_DB = 11
MIC_SAMPLE_COUNT = 256
MIC_SAMPLE_PERIOD_US = 100

# Analog amplifier: PAM8403.
# Audio playback is not yet driven by main.py. GPIO17 is reserved for a
# future PWM audio output stage; it is not connected to the microphone.
AMP_AUDIO_OUT = 17

# Three buttons, active LOW, other side connected to GND.
BUTTON_BACK = 14
BUTTON_MODE = 18
BUTTON_ACTION = 21
BUTTON_DEBOUNCE_MS = 35

# Main loop
FRAME_RATE = 20
FRAME_TIME_MS = 1000 // FRAME_RATE

# Wi-Fi. Fill these locally before using network features.
WIFI_SSID = ""
WIFI_PASSWORD = ""
WIFI_CONNECT_TIMEOUT_MS = 12000
WIFI_RETRY_MS = 10000

# MAX4466 sound classification thresholds.
# Values are in approximately 12-bit ADC counts after DC-offset removal.
# They are intentionally starting values and should be calibrated on the
# assembled robot because MAX4466 gain is adjustable.
AUDIO_SILENCE_RMS = 18
AUDIO_LOUD_RMS = 300
AUDIO_SPEECH_ZCR_MIN = 0.04
AUDIO_SPEECH_ZCR_MAX = 0.25
AUDIO_EVENT_HOLD_MS = 900
AUDIO_SILENCE_HOLD_MS = 700

# Face animation
EMOTION_TRANSITION_MS = 420
BLINK_MIN_MS = 3000
BLINK_MAX_MS = 6500
BLINK_DURATION_MS = 120
