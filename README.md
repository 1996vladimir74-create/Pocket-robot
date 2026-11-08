# Pocket Robot V1

ESP32-S3 desktop companion robot. V1 runs locally on the ESP32-S3 with MicroPython: the controller reads buttons and the MAX4466 analog microphone, updates the emotion state, animates the face and drives the ST7789 display.

## Hardware target
- ESP32-S3-DevKitC-1 N16R8
- ST7789V3 1.69" 240x280 SPI display
- MAX4466 analog microphone amplifier, powered from 3.3 V
- MAX98357A I2S class-D amplifier (mono)
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
MAX98357A <────────────────── speaker.py (I2S tones, software volume)
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

To keep the face from flickering, events are filtered:
- a new sound class is accepted after `AUDIO_CONFIRM_WINDOWS` windows in a row (a loud clap is accepted at once)
- a pause shorter than `AUDIO_SILENCE_HOLD_MS` does not count as silence
- while a sound continues, its event is repeated every `AUDIO_EVENT_HOLD_MS`
- `mute_for()` makes the microphone deaf while the speaker plays, so the robot does not hear itself

This is deliberately a **V1 heuristic**, not speech recognition or a reliable music classifier. Thresholds are in `firmware/config.py` and must be calibrated after the real microphone is connected: run `import calibrate_mic` on the board.

## Display driver

`firmware/display.py` is an ST7789 driver built on MicroPython's native `framebuf` (drawing runs at C speed):
- hardware reset, RGB565 mode, black first frame before the backlight is switched on
- one 134 KB frame buffer allocated once (**needs PSRAM**: flash an `ESP32_GENERIC_S3` build with `SPIRAM_OCT`)
- only the rows that changed since the previous frame are sent over SPI (`DISPLAY_PARTIAL`)
- rectangles, lines, ellipses and arcs

SPI speed, panel offsets, colour order and inversion are configurable in `firmware/config.py`.

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
| MAX98357A | BCLK | 15 |
| MAX98357A | LRC (word select) | 16 |
| MAX98357A | DIN | 17 |
| MAX98357A | SD (enable, optional) | 4 |
| BACK | button | 14 |
| MODE | button | 18 |
| ACTION | button | 21 |

GPIO1 is used for the microphone because it is an ADC1 input (GPIO1-10) on the ESP32-S3. ADC2 (GPIO11-20) conflicts with Wi-Fi operation, so do not use those pins for analog input. Do not use GPIO35-37 (reserved for the octal PSRAM on N16R8 modules).

## Speaker and volume

Wiring of the MAX98357A breakout: `VIN` to the 5 V rail, `GND` to ground, `BCLK`/`LRC`/`DIN` to GPIO15/16/17, `SD` to GPIO4, `GAIN` left unconnected (9 dB). Put a 100 µF capacitor close to `VIN`: the 5 V rail comes from a boost converter and a class-D amplifier draws current in bursts. GPIO4 drives `SD` high only while a sound is playing, which avoids idle hiss and clicks; set `AMP_SD = None` in `config.py` if you do not wire it.

The MAX98357A is a **mono** amplifier and needs a load of **4 ohm or more**. Two 8 ohm speakers in parallel give 4 ohm and are fine; two 4 ohm speakers must be wired in series (8 ohm). Check the impedance printed on your speakers.

Volume is applied in software (the chip has no volume input): the sample amplitude is scaled with a perceptual curve (amplitude ~ volume²). The firmware starts at `SPEAKER_VOLUME` (40 %).

**Volume buttons** (hold, the two outer buttons):

| Hold | Effect |
|---|---|
| MODE | volume up, 5 % every 250 ms while held |
| BACK | volume down |

A short press keeps its normal function (MODE: next face, BACK: neutral face). While you change the volume, ten bars appear at the bottom of the screen and a short tick sounds at the new level. Directions, step size and hold times are in `config.py` (`VOLUME_UP_BUTTON`, `VOLUME_DOWN_BUTTON`, `VOLUME_STEP`, `VOLUME_LONG_PRESS_MS`, `VOLUME_REPEAT_MS`). The volume is not stored: after a restart it returns to `SPEAKER_VOLUME`.

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
    +----> MAX98357A VIN

ESP32-S3 3.3 V ----> ST7789 VCC
                  +-> MAX4466 VCC
```

The MT3608 output must be adjusted and measured at 5.0 V before the 5 V rail is connected to the ESP32-S3 or MAX98357A.

## Wi-Fi

`firmware/wifi.py` connects and reconnects without ever blocking the main loop. SSID/password are intentionally blank in `firmware/config.py`. Copy `firmware/config_local.example.py` to `firmware/config_local.py` and enter them there: that file is in `.gitignore`, so the password never reaches GitHub.

The future network layer will not contain AI logic. The intended architecture remains:

```text
ESP32-S3 = body + reflexes + display + microphone + local emotions
Python server = messages + APIs + memory + future tools
AI model = future intelligence
```

## Flashing / bring-up plan

1. Verify ESP32-S3 board revision and GPIO labels.
2. Flash a current ESP32-S3 MicroPython build **with PSRAM** (`ESP32_GENERIC_S3`, `SPIRAM_OCT`). Check in the REPL: `import gc; gc.collect(); print(gc.mem_free())` should print megabytes, not hundreds of kilobytes.
3. Upload the contents of `firmware/` to the **root** of the board (not into a subfolder), for example:
   `mpremote connect auto fs cp firmware/*.py :` (or drag the files in Thonny).
4. Check the serial boot log: `mpremote connect auto repl`.
5. Test ST7789 alone: `import test_display` (colour bars + edge frame; adjust offsets/colour order in `config.py`).
6. Test the three buttons: short press MODE cycles through all faces, ACTION = happy + beep, BACK = neutral; **hold MODE = volume up, hold BACK = volume down**.
7. Connect MAX4466 to GPIO1 and calibrate the ADC thresholds: `import calibrate_mic`.
8. Test the MAX98357A output path separately: `import test_speaker` (starts very quiet), then try the volume buttons.
9. Run the complete main loop (reset the board; `main.py` starts automatically). The serial line shows `render=..ms`; raise `FRAME_RATE` and `DISPLAY_SPI_BAUD` only while that stays well below the frame time.
10. Only then connect the future server/API layer.

Run the PC-side tests (no hardware needed) with `python -m unittest discover -s tests`.

## Important V1 limitation

The firmware is prepared for the selected architecture, but the audio thresholds and the MAX98357A speaker path have not yet been validated on the physical assembled robot. The first hardware session should therefore be a controlled bring-up rather than powering every module at once.

## Repository layout

```text
firmware/
├── main.py                 # main MicroPython loop
├── config.py               # all GPIO and tuning constants
├── config_local.example.py # template for Wi-Fi secrets (copy to config_local.py)
├── robot.py                # robot state
├── emotion.py              # events + smooth emotion transitions
├── face.py                 # procedural animated face
├── display.py              # ST7789 driver on framebuf, partial updates
├── audio.py                # MAX4466 ADC + local sound classifier with event hold
├── speaker.py              # MAX98357A I2S tones + volume (non-blocking)
├── buttons.py              # three debounced buttons
├── wifi.py                 # non-blocking Wi-Fi helper
├── test_display.py         # bring-up tool: display alone
├── test_speaker.py         # bring-up tool: speaker alone
└── calibrate_mic.py        # bring-up tool: microphone thresholds

tests/
├── test_robot.py           # robot, emotion and face logic
├── test_hardware.py        # audio, display, speaker, main loop (fake hardware)
└── fakes.py                # PC stand-ins for machine / framebuf / SPI
```
