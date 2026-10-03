# Pocket Robot V1

ESP32-S3 desktop companion robot. The project is designed in layers so the same core logic can start on a PC and later run on the ESP32-S3 with MicroPython.

## Hardware target
- ESP32-S3-DevKitC-1 N16R8
- ST7789V3 1.69" 240x280 SPI display
- INMP441 I2S microphone
- MAX98357A I2S amplifier module
- 3 physical buttons
- Li-Po battery + TP4056 + 5V boost converter

## Software architecture

The project separates **what the robot feels** from **how the face is drawn**.

event -> EmotionController -> FaceRenderer -> ST7789 display driver -> real pixels

### EmotionController

Decides the current emotion and state:
- emotions: neutral, happy, sad, sleepy, surprised, angry
- states: idle, listening, thinking, music, sleeping
- intensity: 0.0 to 1.0
- temporary emotions can expire
- hardware events are converted into robot behaviour

### FaceRenderer

`firmware/face.py` converts an emotion into geometry instead of storing a bitmap for every face.

A face is assembled from primitives such as eyes, pupils, eyebrows and mouth. The renderer returns commands such as `fill_ellipse`, `line`, `arc` and `fill_rect`. Later, `display.py` will translate each command into the actual ST7789 library calls.

This means:
- emotions can change without editing image files;
- intensity can change eye and mouth size;
- animation can be generated frame-by-frame;
- the same face logic can be tested on a PC;
- the ESP32 does not need to store many full-screen images.

## Development stages
1. Robot core and state model
2. Emotion/state machine
3. **Procedural face renderer**
4. Display driver for ST7789
5. Buttons
6. Audio
7. Wi-Fi
8. Robot HTTP API
9. Server-side AI agent
10. Memory and tools

## Current stage

**Task 3 — Procedural face renderer**

The emotion system now produces drawing commands for a 240x280 face. The next hardware-facing step is implementing the ST7789 display driver that executes those commands.

## Run tests

`python -m unittest discover -s tests -v`

## Run demo

`python firmware/main.py`