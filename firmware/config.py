"""Hardware configuration for Pocket Robot V1.

Pin numbers are the current planned wiring for ESP32-S3-DevKitC-1 N16R8.
The V1 prototype uses an analog MAX4466 microphone and a MAX98357A I2S amplifier.
The microphone can later be replaced by an INMP441 without changing the
higher-level emotion architecture.

Secrets (Wi-Fi) go into config_local.py (see config_local.example.py);
that file is listed in .gitignore and is never pushed to GitHub.
"""

DEVICE_NAME = "PocketRobot"

# ---------------------------------------------------------------- Display
# 1.69 inch ST7789V3, 240x280, SPI
DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 280
# ESP32-S3: SPI id 1 = SPI2 (GPIO10-13 are its fast native pins).
# If the screen stays blank, try 2.
DISPLAY_SPI_ID = 1
# Start with 20 MHz. Raise to 40000000 only when the picture is stable
# (long wires on a breadboard often break at 40 MHz).
DISPLAY_SPI_BAUD = 20000000
DISPLAY_SCK = 12
DISPLAY_MOSI = 11
DISPLAY_CS = 10
DISPLAY_DC = 9
DISPLAY_RST = 8
DISPLAY_BL = 7
# MADCTL: 0x00 = normal, RGB order. 0x08 = swap red/blue if colours are wrong.
# 0xC0 = rotate 180 degrees (then the offsets below may need to change).
DISPLAY_MADCTL = 0x00
# The 240x280 glass sits inside a 240x320 controller RAM: most panels need
# Y offset 20 at MADCTL 0x00. If you see a garbage strip at the top or
# bottom edge, adjust this (test_display.py helps).
DISPLAY_X_OFFSET = 0
DISPLAY_Y_OFFSET = 20
DISPLAY_INVERT = True
# Send only the rows that changed (faster). Set False to debug.
DISPLAY_PARTIAL = True

# ------------------------------------------------------------- Microphone
# MAX4466 -> ESP32-S3 ADC1. GPIO1 is ADC1_CH0 (ADC2 = GPIO11-20 conflicts
# with Wi-Fi; there is no GPIO25 on the ESP32-S3).
MIC_ADC_PIN = 1
MIC_SAMPLE_COUNT = 128        # window length (samples)
MIC_SAMPLE_PERIOD_US = 100    # pause between samples
MIC_EVERY_N_FRAMES = 2        # listen every N-th frame to leave time for drawing

# ---------------------------------------------------------------- Speaker
# MAX98357A I2S class-D amplifier (mono, output = (left + right) / 2).
# Wiring: BCLK -> AMP_I2S_BCLK, LRC -> AMP_I2S_LRC, DIN -> AMP_I2S_DIN,
# VIN -> 5 V rail, GND -> GND, GAIN left floating (9 dB).
AMP_I2S_ID = 0
AMP_I2S_BCLK = 15
AMP_I2S_LRC = 16
AMP_I2S_DIN = 17
# SD pin of the amplifier: driven high only while a sound is playing (no
# idle hiss, no clicks). Set to None if SD is not wired (the breakout's own
# pull-up then keeps the amplifier always on).
AMP_SD = 4
AUDIO_SAMPLE_RATE = 16000
AUDIO_I2S_IBUF = 8192
# Peak value of the 16-bit samples at 100 % volume (32767 = digital maximum).
AUDIO_MAX_AMPLITUDE = 24000
SPEAKER_VOLUME = 40           # start volume, percent 0..100 (start quiet!)

# Volume control: hold MODE (louder) or BACK (quieter). A short press keeps
# its normal function. Swap the two names to reverse the directions.
VOLUME_UP_BUTTON = "mode"
VOLUME_DOWN_BUTTON = "back"
VOLUME_STEP = 5               # percent per step
VOLUME_LONG_PRESS_MS = 600    # how long to hold before it starts changing
VOLUME_REPEAT_MS = 250        # step repeat interval while still held
VOLUME_BAR_MS = 1500          # how long the volume bar stays on screen

# ---------------------------------------------------------------- Buttons
# Three buttons, active LOW, other side connected to GND.
BUTTON_BACK = 14
BUTTON_MODE = 18
BUTTON_ACTION = 21
BUTTON_DEBOUNCE_MS = 35

# -------------------------------------------------------------- Main loop
FRAME_RATE = 15               # raise when the debug line shows render time << frame time
FRAME_TIME_MS = 1000 // FRAME_RATE
USE_WDT = False               # watchdog: enable only after the robot runs on its own

# ------------------------------------------------------------------ Wi-Fi
# Leave blank here. Put real values in config_local.py.
WIFI_SSID = ""
WIFI_PASSWORD = ""
WIFI_CONNECT_TIMEOUT_MS = 12000
WIFI_RETRY_MS = 10000

# ------------------------------------------------ Sound classification
# Values are in ~12-bit ADC counts after DC-offset removal. They are
# starting values: calibrate with calibrate_mic.py on the assembled robot
# (MAX4466 gain is adjustable).
AUDIO_SILENCE_RMS = 18
AUDIO_LOUD_RMS = 300
AUDIO_SPEECH_ZCR_MIN = 0.04
AUDIO_SPEECH_ZCR_MAX = 0.25
AUDIO_EVENT_HOLD_MS = 900     # while a sound continues, repeat its event this often
AUDIO_SILENCE_HOLD_MS = 700   # a pause shorter than this does not count as silence
AUDIO_CONFIRM_WINDOWS = 2     # a new sound class must be seen this many windows in a row
AUDIO_MUTE_AFTER_SOUND_MS = 250   # extra deaf time after the speaker stops

# ------------------------------------------------------- Face animation
EMOTION_TRANSITION_MS = 420
# Not used yet: blinking in face.py is driven by the frame counter.
BLINK_MIN_MS = 3000
BLINK_MAX_MS = 6500
BLINK_DURATION_MS = 120

# Local overrides (Wi-Fi password etc.). Optional file, not in git.
try:
    from config_local import *  # noqa
except ImportError:
    pass
