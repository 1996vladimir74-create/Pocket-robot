"""Pocket Robot V1 main firmware entry point for MicroPython."""

import time
import config
from robot import Robot
from emotion import EmotionController
from face import FaceRenderer
from display import ST7789
from audio import AudioAnalyzer
from buttons import Buttons
from wifi import WiFiManager


def _handle_button(name, emotions, now_ms):
    if name == "action":
        emotions.handle_event("button_action", now_ms)
    elif name == "mode":
        emotions.handle_event("sound_speech", now_ms)
    elif name == "back":
        emotions.handle_event("silence", now_ms)


def main():
    print("Pocket Robot V1")
    print("ESP32-S3 / MicroPython")

    robot = Robot()
    emotions = EmotionController(config.EMOTION_TRANSITION_MS)
    face = FaceRenderer(config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT)

    display = None
    audio = None
    buttons = None
    wifi = None

    # Hardware is initialized independently so one missing module does not
    # prevent serial debugging of the rest of the firmware.
    try:
        display = ST7789()
        print("Display: OK")
    except Exception as exc:
        print("Display ERROR:", exc)

    try:
        audio = AudioAnalyzer()
        print("Microphone: OK")
    except Exception as exc:
        print("Microphone ERROR:", exc)

    try:
        buttons = Buttons()
        print("Buttons: OK")
    except Exception as exc:
        print("Buttons ERROR:", exc)

    try:
        wifi = WiFiManager()
        wifi.connect()
        print("Wi-Fi:", wifi.status())
    except Exception as exc:
        print("Wi-Fi ERROR:", exc)

    now = time.ticks_ms()
    emotions.handle_event("boot", now)
    last_frame = now
    frame = 0
    last_debug = now

    while True:
        now = time.ticks_ms()
        dt = time.ticks_diff(now, last_frame)
        if dt < config.FRAME_TIME_MS:
            time.sleep_ms(max(1, config.FRAME_TIME_MS - dt))
            continue
        last_frame = now

        # 1. Physical controls
        if buttons is not None:
            try:
                for event in buttons.poll(now):
                    _handle_button(event, emotions, now)
            except Exception as exc:
                print("Button ERROR:", exc)

        # 2. Microphone -> event -> emotion
        if audio is not None:
            try:
                event = audio.sample(now)
                if event is not None:
                    emotions.handle_event(event, now)
            except Exception as exc:
                print("Audio ERROR:", exc)

        # 3. Advance smooth visual transition and timed emotions
        status = emotions.update(dt, now)
        robot.set_mood(status["emotion"], status["intensity"])
        robot.set_state(status["state"])

        # 4. Render current face
        commands = face.render(
            status["to_emotion"],
            status["visual_intensity"],
            frame=frame,
            from_emotion=status["from_emotion"],
            blend=status["visual_blend"],
        )
        if display is not None:
            try:
                display.render(commands)
            except Exception as exc:
                print("Display ERROR:", exc)

        # 5. Maintain Wi-Fi for future server/API integration
        if wifi is not None:
            try:
                wifi.maintain()
                robot.set_wifi(wifi.connected)
            except Exception as exc:
                print("Wi-Fi ERROR:", exc)

        # Serial diagnostics once per second
        if time.ticks_diff(now, last_debug) >= 1000:
            last_debug = now
            if audio is not None:
                print("emotion={}, state={}, audio={}".format(
                    status["emotion"], status["state"], audio.status()))
            else:
                print("emotion={}, state={}".format(status["emotion"], status["state"]))

        frame += 1


if __name__ == "__main__":
    main()
