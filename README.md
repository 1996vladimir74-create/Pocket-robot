# Pocket Robot V1

ESP32-S3 desktop companion robot. The project is designed in layers so the same core logic can start on a PC and later run on the ESP32-S3 with MicroPython.

## Hardware target
- ESP32-S3-DevKitC-1 N16R8
- ST7789V3 1.69" 240x280 SPI display
- INMP441 I2S microphone
- MAX98357A I2S amplifier module
- 3 physical buttons
- Li-Po battery + TP4056 + 5V boost converter

## Development stages
1. Robot core and state model
2. Emotion/state machine
3. Display
4. Buttons
5. Audio
6. Wi-Fi
7. Robot HTTP API
8. Server-side AI agent
9. Memory and tools

## Current stage
**Task 1 — Robot core**

The first implementation uses only standard Python, so it can be tested before the hardware arrives.

## Run tests
```bash
python -m unittest discover -s tests -v
```

## Run demo
```bash
python firmware/main.py
```
