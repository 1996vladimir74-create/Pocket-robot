# Pocket Robot V1

ESP32-S3 desktop companion robot. V1 is designed to run locally on the ESP32-S3 with MicroPython: the controller reads buttons and the INMP441 microphone, updates the emotion state, animates the face and drives the ST7789 display.

## Hardware target
- ESP32-S3-DevKitC-1 N16R8
- ST7789V3 1.69" 240x280 SPI display
- INMP441 I2S microphone
- MAX98357A I2S amplifier module
- 3 physical buttons: MODE, ACTION, BACK
- Li-Po + TP4056 + 5V boost converter

## Current firmware architecture

```text
buttons ─────────────┐
                     │
INMP441 ─> Audio ─> event ─> EmotionController
                     │              │
                     │              ▼
                     │       smooth transition
                     │              │
                     │              ▼
                     └──────> FaceRenderer
                                    │
                                    ▼
                              ST7789 driver
                                    │
                                    ▼
                                240x280 pixels

Wi-Fi ───────────────────────> future HTTP/API layer
MAX98357A <────────────────── future sound/TTS layer
```

## EmotionController

Supported emotions:
- neutral
- happy
- sad
- sleepy
- surprised
- angry

Supported states:
- idle
- listening
- thinking
- music
- sleeping

The controller accepts events such as `sound_speech`, `sound_music`, `sound_noise`, `silence`, `button_action`, `message_received` and `ai_thinking`.

Emotion changes are not switched instantly. The controller exposes `from_emotion`, `to_emotion` and `visual_blend`, allowing the face to morph between two emotion profiles.

## FaceRenderer

`firmware/face.py` creates the face procedurally from geometry. There are no bitmap files for the emotions.

The renderer uses profiles for:
- eye openness
- eyebrow angle
- mouth curve
- mouth opening

These parameters are interpolated during a transition, so the face can move from neutral -> surprised -> happy -> sleepy instead of jumping between unrelated images.

The renderer returns simple commands such as `fill_rect`, `fill_ellipse`, `line` and `arc`. `display.py` converts them into pixels.

## Audio reactions

`firmware/audio.py` reads the INMP441 through MicroPython I2S and calculates two lightweight features:
- RMS level
- zero-crossing rate

V1 uses these features for a local heuristic classifier:
- silence -> neutral/idle
- speech-like sound -> listening
- medium periodic/low-ZCR sound -> music-like/happy
- loud sound -> surprised

This is deliberately a **V1 heuristic**, not speech recognition or a reliable music classifier. Thresholds are in `firmware/config.py` and will be calibrated after the real microphone is connected.

MicroPython's current I2S API supports ESP32 RX/TX operation with configurable pins, sample width, mono/stereo format and sample rate. citeturn0search0turn0search1

## Display driver

`firmware/display.py` contains a small ST7789 driver with:
- hardware reset
- RGB565 mode
- SPI window addressing
- full-frame buffer
- rectangles
- lines
- ellipses
- arcs

The display module's exact offsets/rotation remain configurable in `firmware/config.py`, because the physical 1.69" module must be checked when it arrives.

## Pin configuration

The current planned mapping is centralized in `firmware/config.py`:

| Device | Signal | GPIO |
|---|---|---:|
| ST7789 | SCK | 12 |
| ST7789 | MOSI | 11 |
| ST7789 | CS | 10 |
| ST7789 | DC | 9 |
| ST7789 | RST | 8 |
| ST7789 | BL | 7 |
| INMP441 | BCLK | 4 |
| INMP441 | WS | 5 |
| INMP441 | SD | 6 |
| MAX98357A | BCLK | 15 |
| MAX98357A | WS/LRC | 16 |
| MAX98357A | DIN | 17 |
| BACK | button | 14 |
| MODE | button | 18 |
| ACTION | button | 21 |

**Important:** this is the planned V1 map. Verify the physical module pinout before soldering. The ESP32 port documentation notes that GPIO availability can be board-specific, so the actual board pin diagram remains the final authority. citeturn1search4

## Wi-Fi

`firmware/wifi.py` provides connection and reconnection logic. SSID/password are intentionally blank in the repository and must be entered locally in `firmware/config.py` before network use.

The future network layer will not contain AI logic. The intended architecture remains:

```text
ESP32-S3 = body + reflexes + display + microphone + local emotions
Python server = messages + APIs + memory + future tools
AI model = future intelligence
```

## Flashing plan

The repository is now prepared as a MicroPython V1 firmware tree. When the hardware arrives, the first bring-up should be performed in this order:

1. Verify ESP32-S3 board revision and GPIO labels.
2. Flash a current ESP32-S3 MicroPython firmware.
3. Upload the contents of `firmware/` to the board.
4. Check the serial boot log.
5. Test ST7789 alone and correct `DISPLAY_ROTATION`/offsets if required.
6. Test the three buttons.
7. Test INMP441 levels and calibrate audio thresholds.
8. Test MAX98357A/speaker.
9. Run the complete main loop.
10. Only then connect the future server/API layer.

## Important V1 limitation

The code is prepared for the selected hardware, but it has **not been tested on the physical modules yet**. In particular, the exact ST7789 module initialization/offsets and the INMP441 signal level must be verified on the actual boards. The first firmware session should therefore be a controlled hardware bring-up rather than blindly powering every module at once.

## Repository layout

```text
firmware/
├── main.py       # main MicroPython loop
├── config.py     # all GPIO and tuning constants
├── robot.py      # robot state
├── emotion.py    # events + smooth emotion transitions
├── face.py       # procedural animated face
├── display.py    # ST7789 SPI driver
├── audio.py      # INMP441 + local sound classifier
├── speaker.py    # MAX98357A I2S output
├── buttons.py    # three debounced buttons
└── wifi.py       # Wi-Fi connection helper

tests/
└── test_robot.py # PC-side tests for hardware-independent logic
```
