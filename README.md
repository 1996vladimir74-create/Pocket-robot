# Pocket Robot V1

ESP32-S3 desktop companion robot. V1 runs locally on the ESP32-S3 with MicroPython: the controller reads buttons and the MAX4466 analog microphone, updates the emotion state, animates the face and drives the ST7789 display.

## Hardware target
- ESP32-S3-DevKitC-1 N16R8
- ST7789V3 1.69" 240x280 SPI display
- MAX4466 analog microphone amplifier, powered from 3.3 V
- PAM8403 stereo analog amplifier
- 2 small speakers
- 3 physical buttons: MODE, ACTION, BACK
- Li-Po + TP4056 + MT3608 5 V boost converter

The MAX4466 is the temporary V1 microphone. The architecture keeps the
microphone behind `AudioAnalyzer`, so an INMP441 I2S microphone can replace it
later without changing the emotion engine or face renderer.

## Current firmware architecture

```text
buttons ─────────────┐
                     │
MAX4466 -> ADC -> Audio -> event -> EmotionController
                                      │
                                      ▼
                               smooth transition
                                      │
                                      ▼
                                  FaceRenderer
                                      │
                                      ▼
                                 ST7789 driver
                                      │
                                      ▼
                                  240x280 pixels

Wi-Fi ───────────────────────> future HTTP/API layer
PAM8403 <──────────────────── future PWM tone/output layer
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

`firmware/audio.py` reads the MAX4466 analog output through an ESP32-S3 ADC1 pin and calculates two lightweight features:
- AC RMS level after DC-offset removal
- zero-crossing rate

The MAX4466 output is DC-biased around VCC/2, so the firmware estimates the center value for each sample window before calculating the AC signal level.

V1 uses these features for a local heuristic classifier:
- silence -> neutral/idle
- speech-like sound -> listening
- medium periodic/low-ZCR sound -> music-like/happy
- loud sound -> surprised

This is deliberately a **V1 heuristic**, not speech recognition or a reliable music classifier. Thresholds are in `firmware/config.py` and must be calibrated after the real microphone is connected.

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

The display module's exact offsets/rotation remain configurable in `firmware/config.py`.

## Pin configuration

The current mapping is centralized in `firmware/config.py`:

| Device | Signal | GPIO |
|---|---|---:|
| ST7789 | SCK | 12 |
| ST7789 | MOSI | 11 |
| ST7789 | CS | 10 |
| ST7789 | DC | 9 |
| ST7789 | RST | 8 |
| ST7789 | BL | 7 |
| MAX4466 | OUT / ADC1 | 1 |
| PAM8403 | PWM audio input | 17 |
| BACK | button | 14 |
| MODE | button | 18 |
| ACTION | button | 21 |

GPIO1 is used for the microphone because it is an ADC1 input on the ESP32-S3. Avoid using GPIO25 for this purpose: GPIO25 is an ADC2 channel on ESP32-S3, and ADC2 conflicts with Wi-Fi operation.

## Power architecture

```text
Li-Po 3.7 V
    |
  TP4056
    |
 ON/OFF
    |
 MT3608 adjusted to 5.0 V
    |
    +----> ESP32-S3 5V
    |
    +----> PAM8403 VCC

ESP32-S3 3.3 V ----> ST7789 VCC
                  +-> MAX4466 VCC
```

The MT3608 output must be adjusted and measured at 5.0 V before the 5 V rail is connected to the ESP32-S3 or PAM8403.

## Wi-Fi

`firmware/wifi.py` provides connection and reconnection logic. SSID/password are intentionally blank in the repository and must be entered locally in `firmware/config.py` before network use.

The future network layer will not contain AI logic. The intended architecture remains:

```text
ESP32-S3 = body + reflexes + display + microphone + local emotions
Python server = messages + APIs + memory + future tools
AI model = future intelligence
```

## Flashing / bring-up plan

1. Verify ESP32-S3 board revision and GPIO labels.
2. Flash a current ESP32-S3 MicroPython firmware.
3. Upload the contents of `firmware/` to the board.
4. Check the serial boot log.
5. Test ST7789 alone.
6. Test the three buttons.
7. Connect MAX4466 to GPIO1 and calibrate the ADC sound thresholds.
8. Test the PAM8403 output path separately.
9. Run the complete main loop.
10. Only then connect the future server/API layer.

## Important V1 limitation

The firmware is prepared for the selected architecture, but the audio thresholds and PAM8403 tone path have not yet been validated on the physical assembled robot. The first hardware session should therefore be a controlled bring-up rather than powering every module at once.

## Repository layout

```text
firmware/
├── main.py       # main MicroPython loop
├── config.py     # all GPIO and tuning constants
├── robot.py      # robot state
├── emotion.py    # events + smooth emotion transitions
├── face.py       # procedural animated face
├── display.py    # ST7789 SPI driver
├── audio.py      # MAX4466 ADC + local sound classifier
├── speaker.py    # PAM8403 PWM tone output
├── buttons.py    # three debounced buttons
└── wifi.py       # Wi-Fi connection helper

tests/
└── test_robot.py # PC-side tests for hardware-independent logic
```
