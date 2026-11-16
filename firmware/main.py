"""Pocket Robot V1 main firmware entry point for MicroPython."""

import gc
import time
import config
from robot import Robot
from emotion import EmotionController
from face import FaceRenderer
from display import ST7789
from audio import AudioAnalyzer
from speaker import Speaker
from buttons import Buttons
from wifi import WiFiManager
from server_client import ServerClient
try:
    from ble_bridge import BLEBridge
except ImportError:
    BLEBridge = None

# MODE button cycles through these faces (handy for the first bring-up).
DEMO_EMOTIONS = ("happy", "sad", "sleepy", "surprised", "angry", "neutral")

_error_counts = {}


def _report(name, exc):
    """Print an error once, then only every 100th repeat (no console spam)."""
    count = _error_counts.get(name, 0) + 1
    _error_counts[name] = count
    if count == 1 or count % 100 == 0:
        print("{} ERROR (x{}): {}".format(name, count, exc))


def _ok(name):
    _error_counts[name] = 0


def _beep(speaker, audio, now_ms, notes):
    """Play notes and keep the microphone deaf so the robot doesn't hear itself."""
    if speaker is None:
        return
    speaker.play_sequence(notes, now_ms)
    if speaker.busy and audio is not None:
        audio.mute_for(now_ms, speaker.playback_ms(notes)
                       + config.AUDIO_MUTE_AFTER_SOUND_MS)


def _change_volume(delta, robot, speaker, audio, now_ms, ctx):
    """Long press of the outer buttons: change volume, show the bar, tick."""
    if speaker is None:
        return
    volume = speaker.set_volume(speaker.volume + delta)
    robot.set_volume(volume)
    ctx["bar_until"] = time.ticks_add(now_ms, config.VOLUME_BAR_MS)
    _beep(speaker, audio, now_ms, ((1000, 30),))


def _handle_button(name, emotions, robot, speaker, audio, now_ms, ctx):
    if name == config.VOLUME_UP_BUTTON + "_hold":
        _change_volume(config.VOLUME_STEP, robot, speaker, audio, now_ms, ctx)
    elif name == config.VOLUME_DOWN_BUTTON + "_hold":
        _change_volume(-config.VOLUME_STEP, robot, speaker, audio, now_ms, ctx)
    elif name == "action":
        emotions.handle_event("button_action", now_ms)
        _beep(speaker, audio, now_ms, ((880, 70), (1175, 90)))
    elif name == "mode":
        if robot.message is not None:
            robot.clear_message()
            ctx["message_id"] = None
            ctx["message_acked"] = False
            ctx["message_until"] = None
            ctx["weather_until"] = None
        else:
            ctx["demo"] = (ctx["demo"] + 1) % len(DEMO_EMOTIONS)
            emotions.set_emotion(DEMO_EMOTIONS[ctx["demo"]], 0.8, 3000, now_ms)
    elif name == "back":
        if speaker is not None:
            speaker.stop()
        emotions.set_emotion("neutral", 0.5, None, now_ms)


def main():
    print("Pocket Robot V1")
    print("ESP32-S3 / MicroPython")

    robot = Robot()
    emotions = EmotionController(config.EMOTION_TRANSITION_MS)
    face = FaceRenderer(config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT)

    display = None
    audio = None
    speaker = None
    buttons = None
    wifi = None
    server_client = None
    ble_bridge = None
    wdt = None

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
        speaker = Speaker()
        robot.set_volume(speaker.volume)
        print("Speaker: OK")
    except Exception as exc:
        print("Speaker ERROR:", exc)

    try:
        buttons = Buttons()
        print("Buttons: OK")
    except Exception as exc:
        print("Buttons ERROR:", exc)

    try:
        wifi = WiFiManager()  # the connection is started later by wifi.maintain()
        print("Wi-Fi: manager ready" if config.WIFI_SSID else "Wi-Fi: no SSID set")
    except Exception as exc:
        print("Wi-Fi ERROR:", exc)

    if getattr(config, "SERVER_HOST", "") and getattr(config, "SERVER_DEVICE_TOKEN", ""):
        try:
            server_client = ServerClient(config.SERVER_HOST, config.SERVER_PORT,
                                          config.SERVER_DEVICE_TOKEN,
                                          getattr(config, "SERVER_TIMEOUT_S", 2))
            print("Message server: configured")
        except Exception as exc:
            _report("Message server init", exc)

    if BLEBridge is not None:
        try:
            ble_bridge = BLEBridge(config.DEVICE_NAME)
            print("BLE bridge: advertising")
        except Exception as exc:
            _report("BLE init", exc)

    if config.USE_WDT:
        try:
            from machine import WDT
            wdt = WDT(timeout=8000)
            print("Watchdog: ON")
        except Exception as exc:
            print("Watchdog ERROR:", exc)

    ctx = {"demo": -1, "bar_until": None, "message_until": None,
           "message_id": None, "message_acked": False, "last_server_poll": None,
           "last_ack_attempt": None, "last_weather_poll": None,
           "weather": None, "weather_until": None}
    now = time.ticks_ms()
    emotions.handle_event("boot", now)
    status = emotions.status()
    last_frame = now
    frame = 0
    last_debug = now
    render_ms = 0

    while True:
        if wdt is not None:
            wdt.feed()

        now = time.ticks_ms()
        dt = time.ticks_diff(now, last_frame)
        if dt < config.FRAME_TIME_MS:
            time.sleep_ms(max(1, config.FRAME_TIME_MS - dt))
            continue
        last_frame = now

        # 1. Physical controls
        if buttons is not None:
            try:
                for name in buttons.poll(now):
                    _handle_button(name, emotions, robot, speaker, audio, now, ctx)
                _ok("Buttons")
            except Exception as exc:
                _report("Buttons", exc)

        # 1b. iPhone -> BLE notification. MODE dismisses it.
        if ble_bridge is not None:
            try:
                incoming_ble = ble_bridge.poll()
                if incoming_ble == "NEW_MESSAGE":
                    # Consume every BLE event so the phone can acknowledge it.
                    # An already-visible envelope represents additional messages too.
                    if robot.message is None:
                        robot.set_message("NEW_MESSAGE")
                        ctx["message_id"] = None
                        ctx["message_acked"] = False
                        ctx["message_until"] = None
                        ctx["weather_until"] = None
                        emotions.handle_event("message_received", now)
                    print("BLE notification event received")
            except Exception as exc:
                _report("BLE receive", exc)

        # 2. Speaker: move to the next note / stop
        if speaker is not None:
            try:
                speaker.update(now)
                _ok("Speaker")
            except Exception as exc:
                _report("Speaker", exc)

        # 3. Microphone -> event -> emotion (not every frame: leave time for drawing)
        if audio is not None and frame % config.MIC_EVERY_N_FRAMES == 0:
            try:
                event = audio.sample(now)
                if event is not None:
                    emotions.handle_event(event, now)
                _ok("Audio")
            except Exception as exc:
                _report("Audio", exc)

        # 4. Emotions + drawing: one error must not kill the robot
        try:
            status = emotions.update(dt, now)
            robot.set_mood(status["emotion"], status["intensity"])
            robot.set_state(status["state"])

            if robot.message is not None:
                commands = face.message_screen()
            elif (ctx["weather"] is not None and ctx["weather_until"] is not None
                  and time.ticks_diff(now, ctx["weather_until"]) < 0):
                commands = face.weather_screen(ctx["weather"])
            else:
                commands = face.render(
                    status["to_emotion"], status["visual_intensity"], frame=frame,
                    from_emotion=status["from_emotion"], blend=status["visual_blend"])
            if ctx["bar_until"] is not None:
                if time.ticks_diff(now, ctx["bar_until"]) < 0:
                    commands = commands + face.volume_bar(robot.volume)
                else:
                    ctx["bar_until"] = None
            if display is not None:
                started = time.ticks_ms()
                display.render(commands)
                render_ms = time.ticks_diff(time.ticks_ms(), started)
                if (robot.message is not None and ctx["message_id"] is not None
                        and not ctx["message_acked"] and server_client is not None
                        and (ctx["last_ack_attempt"] is None or
                             time.ticks_diff(now, ctx["last_ack_attempt"]) >= 5000)):
                    ctx["last_ack_attempt"] = now
                    try:
                        server_client.acknowledge(ctx["message_id"])
                        ctx["message_acked"] = True
                        print("Message acknowledged:", ctx["message_id"])
                    except Exception as exc:
                        _report("Message ACK", exc)
            _ok("Render")
        except Exception as exc:
            _report("Render", exc)

        # 5. Maintain Wi-Fi (never blocks)
        if wifi is not None:
            try:
                wifi.maintain()
                robot.set_wifi(wifi.connected)
                if wifi.connected and getattr(config, "SERVER_DEVICE_TOKEN", ""):
                    active_host = wifi.server_host
                    if active_host and (server_client is None or server_client.host != active_host):
                        server_client = ServerClient(active_host, config.SERVER_PORT,
                            config.SERVER_DEVICE_TOKEN, getattr(config, "SERVER_TIMEOUT_S", 4))
                        print("Server host selected:", active_host)
                if server_client is not None and wifi.connected:
                    due = (ctx["last_server_poll"] is None or
                           time.ticks_diff(now, ctx["last_server_poll"]) >=
                           getattr(config, "SERVER_POLL_INTERVAL_MS", 15000))
                    if due and robot.message is None:
                        ctx["last_server_poll"] = now
                        try:
                            incoming = server_client.poll()
                            if incoming and incoming.get("id") is not None:
                                robot.set_message("NEW_MESSAGE")
                                ctx["message_id"] = incoming["id"]
                                ctx["message_acked"] = False
                                ctx["last_ack_attempt"] = None
                                ctx["message_until"] = None
                                ctx["weather_until"] = None
                                emotions.handle_event("message_received", now)
                                print("Message received:", incoming["id"])
                        except Exception as exc:
                            _report("Message poll", exc)
                if server_client is not None and wifi.connected:
                    weather_due = (ctx["last_weather_poll"] is None or
                        time.ticks_diff(now, ctx["last_weather_poll"]) >=
                        getattr(config, "WEATHER_POLL_INTERVAL_MS", 600000))
                    if weather_due and robot.message is None:
                        ctx["last_weather_poll"] = now
                        try:
                            ctx["weather"] = server_client.weather()
                            ctx["weather_until"] = time.ticks_add(now, 5000)
                            temp = ctx["weather"].get("temperature_c")
                            robot.set_temperature(temp)
                            print("Weather updated:", temp, "C")
                        except Exception as exc:
                            _report("Weather", exc)
                _ok("Wi-Fi")
            except Exception as exc:
                _report("Wi-Fi", exc)

        # Serial diagnostics once per second
        if time.ticks_diff(now, last_debug) >= 1000:
            last_debug = now
            line = "emotion={} state={} vol={} render={}ms".format(
                status["emotion"], status["state"], robot.volume, render_ms)
            if hasattr(gc, "mem_free"):
                line += " free={}".format(gc.mem_free())
            if audio is not None:
                line += " audio={}".format(audio.status())
            print(line)

        frame += 1
        if frame % 100 == 0:
            gc.collect()


if __name__ == "__main__":
    main()

