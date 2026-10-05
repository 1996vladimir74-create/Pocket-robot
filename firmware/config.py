"""Hardware configuration for Pocket Robot V1.

Pin numbers are the current planned wiring for ESP32-S3-DevKitC-1 N16R8.
When the physical modules arrive, check the silkscreen/pinout and change
ONLY this file if a different GPIO mapping is required.
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

# INMP441 I2S microphone
MIC_I2S_ID = 0
MIC_BCLK = 4
MIC_WS = 5
MIC_SD = 6
MIC_SAMPLE_RATE = 16000
MIC_SAMPLE_BITS = 32
MIC_BUFFER_SAMPLES = 256

# MAX98357A I2S amplifier
AMP_I2S_ID = 1
AMP_BCLK = 15
AMP_WS = 16
AMP_DIN = 17
AMP_SAMPLE_RATE = 16000

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

# Audio classification thresholds. These are heuristic V1 values and will
# be calibrated on the real microphone.
AUDIO_SILENCE_RMS = 350
AUDIO_LOUD_RMS = 2600
AUDIO_SPEECH_ZCR_MIN = 0.04
AUDIO_SPEECH_ZCR_MAX = 0.25
AUDIO_EVENT_HOLD_MS = 900
AUDIO_SILENCE_HOLD_MS = 700

# Face animation
EMOTION_TRANSITION_MS = 420
BLINK_MIN_MS = 3000
BLINK_MAX_MS = 6500
BLINK_DURATION_MS = 120
