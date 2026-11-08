"""PC tests for the hardware-facing modules, using fake hardware (see fakes.py)."""

import contextlib
import io
import math
import os
import re
import sys
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
FIRMWARE_DIR = os.path.join(os.path.dirname(HERE), "firmware")
for path in (HERE, FIRMWARE_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import fakes
fakes.install()

import config
from fakes import ADC, I2S, Pin
from audio import AudioAnalyzer
from display import ST7789
from face import FaceRenderer
import struct
from buttons import Buttons
from speaker import Speaker


class Signal:
    """Synthetic microphone: a sine wave around the ADC centre."""
    FS = 10000.0

    def __init__(self):
        self.amp = 0
        self.freq = 0
        self.center = 2048
        self.phase = 0.0
        self.n = 0

    def __call__(self):
        self.n += 1
        noise = ((self.n * 7919) % 5) - 2          # +-2 counts of fixed "noise"
        value = self.center + noise
        if self.amp:
            self.phase += self.freq / self.FS
            value += self.amp * math.sin(2 * math.pi * self.phase)
        return max(0, min(4095, int(value)))


class AudioTests(unittest.TestCase):
    def setUp(self):
        self._period = config.MIC_SAMPLE_PERIOD_US
        config.MIC_SAMPLE_PERIOD_US = 0
        self.sig = Signal()
        ADC.source = self.sig
        self.mic = AudioAnalyzer()

    def tearDown(self):
        config.MIC_SAMPLE_PERIOD_US = self._period
        ADC.source = None

    def run_schedule(self, schedule, start=0, step=50):
        """schedule: list of (duration_ms, amp, freq). Returns [(time, event)]."""
        events = []
        now = start
        for duration, amp, freq in schedule:
            self.sig.amp, self.sig.freq = amp, freq
            for _ in range(duration // step):
                now += step
                event = self.mic.sample(now)
                if event:
                    events.append((now, event))
        self.now = now
        return events

    def test_classification(self):
        self.assertEqual(self.mic._classify(5, 0.1), "silence")
        self.assertEqual(self.mic._classify(100, 0.10), "sound_speech")
        self.assertEqual(self.mic._classify(100, 0.50), "sound_music")
        self.assertEqual(self.mic._classify(500, 0.10), "sound_noise")

    def test_synthetic_signals_are_classified(self):
        for amp, freq, expected in ((0, 0, "silence"), (150, 500, "sound_speech"),
                                    (150, 2500, "sound_music"), (800, 500, "sound_noise")):
            self.sig.amp, self.sig.freq = amp, freq
            self.mic._read_samples()
            rms, zcr = self.mic._features()
            self.assertEqual(self.mic._classify(rms, zcr), expected, (amp, freq, rms, zcr))

    def test_dc_offset_is_removed(self):
        self.sig.center = 1000
        self.sig.amp, self.sig.freq = 150, 500
        self.mic._read_samples()
        rms, zcr = self.mic._features()
        self.assertTrue(80 < rms < 130, rms)
        self.assertTrue(abs(self.mic.last_center - 1000) < 10)

    def test_speech_needs_confirmation_then_repeats(self):
        events = self.run_schedule([(3000, 150, 500)])
        names = [e for _t, e in events]
        self.assertTrue(set(names) == {"sound_speech"}, names)
        self.assertLessEqual(events[0][0], 150)            # confirmed after 2 windows
        gaps = [b[0] - a[0] for a, b in zip(events, events[1:])]
        self.assertTrue(all(g >= config.AUDIO_EVENT_HOLD_MS for g in gaps), gaps)
        self.assertGreaterEqual(len(events), 3)             # the event is repeated

    def test_short_pause_does_not_flicker(self):
        events = self.run_schedule([(1000, 150, 500), (300, 0, 0), (1000, 150, 500)])
        self.assertNotIn("silence", [e for _t, e in events])

    def test_long_silence_is_reported_once(self):
        events = self.run_schedule([(1000, 150, 500), (3000, 0, 0)])
        silences = [t for t, e in events if e == "silence"]
        self.assertEqual(len(silences), 1)
        self.assertGreaterEqual(silences[0] - 1000, config.AUDIO_SILENCE_HOLD_MS)

    def test_clap_is_immediate(self):
        events = self.run_schedule([(500, 0, 0), (50, 800, 500)])
        self.assertEqual(events[-1][1], "sound_noise")
        self.assertEqual(events[-1][0], 550)

    def test_music_is_detected(self):
        events = self.run_schedule([(1000, 150, 2500)])
        self.assertEqual(events[0][1], "sound_music")

    def test_mute_makes_microphone_deaf(self):
        self.mic.mute_for(0, 500)
        events = self.run_schedule([(450, 800, 500)])
        self.assertEqual(events, [])
        events = self.run_schedule([(400, 800, 500)], start=self.now)
        self.assertTrue(events)                              # works again after the mute

    def test_missing_attenuation_is_an_error(self):
        saved = ADC.ATTN_11DB
        del ADC.ATTN_11DB
        try:
            with self.assertRaises(RuntimeError):
                AudioAnalyzer()
        finally:
            ADC.ATTN_11DB = saved


class SpeakerTests(unittest.TestCase):
    STEP = 66          # ms between frames of the main loop

    def setUp(self):
        I2S.instances = []
        Pin.levels.pop(config.AMP_SD, None)

    def make(self, volume=50):
        s = Speaker()
        s.set_volume(volume)
        return s

    def run_until_idle(self, s, start=0, limit_ms=5000):
        """Drive update() like the main loop; checks the buffer never runs far ahead."""
        now = start
        while s.busy and now - start < limit_ms:
            s.update(now)
            ahead = s.fed * 1000 // s.rate - (now - s.start_ms)
            self.assertLessEqual(ahead, Speaker.LEAD_MS + 20, "queued too far ahead")
            now += self.STEP
        return now

    def samples(self, s):
        data = I2S.instances[0].stream()
        return struct.unpack("<%dh" % (len(data) // 2), data)

    def test_i2s_is_configured_for_the_amplifier(self):
        self.make()
        kw = I2S.instances[0].kwargs
        self.assertEqual(kw["rate"], config.AUDIO_SAMPLE_RATE)
        self.assertEqual(kw["bits"], 16)
        self.assertEqual(kw["format"], I2S.MONO)

    def test_stream_length_covers_notes_with_lead_in_and_tail(self):
        s = self.make()
        s.play_sequence(((880, 100), (0, 50), (1175, 100)), 0)
        self.run_until_idle(s)
        rate = config.AUDIO_SAMPLE_RATE
        frames = sum(rate * ms // 1000 for ms in (Speaker.LEAD_IN_MS, 100, 50, 100, Speaker.TAIL_MS))
        self.assertEqual(len(I2S.instances[0].stream()), frames * 2)
        self.assertFalse(s.busy)

    def test_pitch_is_correct(self):
        s = self.make(80)
        s.play(1000, 200, 0)
        self.run_until_idle(s)
        samples = self.samples(s)
        lead = config.AUDIO_SAMPLE_RATE * Speaker.LEAD_IN_MS // 1000
        note = samples[lead:lead + config.AUDIO_SAMPLE_RATE * 200 // 1000]
        crossings = sum(1 for a, b in zip(note, note[1:]) if (a < 0) != (b < 0))
        self.assertTrue(380 <= crossings <= 420, crossings)      # 1000 Hz * 0.2 s * 2

    def test_volume_scales_the_amplitude(self):
        peaks = {}
        for volume in (20, 50, 100):
            I2S.instances = []
            s = self.make(volume)
            s.play(800, 100, 0)
            self.run_until_idle(s)
            peaks[volume] = max(abs(v) for v in self.samples(s))
        self.assertLess(peaks[20], peaks[50])
        self.assertLess(peaks[50], peaks[100])
        self.assertLessEqual(peaks[100], config.AUDIO_MAX_AMPLITUDE)
        self.assertGreater(peaks[100], config.AUDIO_MAX_AMPLITUDE * 0.9)

    def test_notes_fade_in_and_out_without_clicks(self):
        s = self.make(100)
        s.play(800, 100, 0)
        self.run_until_idle(s)
        samples = self.samples(s)
        lead = config.AUDIO_SAMPLE_RATE * Speaker.LEAD_IN_MS // 1000
        self.assertEqual(samples[lead], 0)
        self.assertLess(abs(samples[lead + 1]), 1500)
        end = lead + config.AUDIO_SAMPLE_RATE * 100 // 1000
        self.assertLess(abs(samples[end - 1]), 1500)

    def test_amplifier_enabled_only_while_playing(self):
        s = self.make()
        self.assertEqual(Pin.levels[config.AMP_SD], 0)
        s.play(880, 100, 0)
        self.assertEqual(Pin.levels[config.AMP_SD], 1)
        self.run_until_idle(s)
        self.assertEqual(Pin.levels[config.AMP_SD], 0)

    def test_volume_zero_plays_nothing(self):
        s = self.make(0)
        s.play(880, 100, 0)
        self.assertFalse(s.busy)
        self.assertEqual(I2S.instances[0].writes, [])
        self.assertEqual(Pin.levels[config.AMP_SD], 0)

    def test_volume_to_zero_silences_a_running_sound(self):
        s = self.make(50)
        s.play(880, 500, 0)
        s.update(0)
        s.set_volume(0)
        self.assertFalse(s.busy)
        self.assertEqual(Pin.levels[config.AMP_SD], 0)

    def test_volume_steps_are_clamped(self):
        s = self.make(98)
        self.assertEqual(s.volume_up(5), 100)
        s.set_volume(3)
        self.assertEqual(s.volume_down(5), 0)
        self.assertEqual(s.set_volume(150), 100)
        self.assertEqual(s.set_volume(-5), 0)

    def test_stop_silences_immediately(self):
        s = self.make()
        s.play(880, 1000, 0)
        s.update(0)
        s.stop()
        self.assertFalse(s.busy)
        self.assertEqual(Pin.levels[config.AMP_SD], 0)
        self.assertTrue(set(I2S.instances[0].writes[-1]) == {0})   # buffer ends with silence

    def test_new_sound_queues_behind_the_old_one(self):
        s = self.make()
        s.play(880, 200, 0)
        s.update(0)
        s.play(1000, 30, 100)                                       # while the first is playing
        self.assertGreater(s.start_ms, 100)
        self.run_until_idle(s, start=100)
        self.assertFalse(s.busy)

    def test_playback_ms(self):
        self.assertEqual(Speaker.playback_ms(((880, 70), (1175, 90))),
                         160 + Speaker.LEAD_IN_MS + Speaker.TAIL_MS)


class ButtonTests(unittest.TestCase):
    def setUp(self):
        for pin in (config.BUTTON_BACK, config.BUTTON_MODE, config.BUTTON_ACTION):
            Pin.levels[pin] = 1
        self.b = Buttons()

    def press(self, pin):
        Pin.levels[pin] = 0

    def release(self, pin):
        Pin.levels[pin] = 1

    def poll_for(self, start, end, step=50):
        events = []
        t = start
        while t <= end:
            for e in self.b.poll(t):
                events.append((t, e))
            t += step
        return events

    def test_action_fires_on_press(self):
        self.press(config.BUTTON_ACTION)
        self.assertEqual(self.b.poll(100), ["action"])
        self.assertEqual(self.b.poll(150), [])

    def test_short_press_of_mode_fires_on_release(self):
        self.press(config.BUTTON_MODE)
        self.assertEqual(self.poll_for(100, 300), [])
        self.release(config.BUTTON_MODE)
        self.assertEqual(self.poll_for(350, 450), [(350, "mode")])

    def test_long_press_repeats_and_has_no_short_press_afterwards(self):
        self.press(config.BUTTON_MODE)
        events = self.poll_for(100, 1700)
        names = [e for _t, e in events]
        self.assertTrue(names and set(names) == {"mode_hold"}, names)
        self.assertGreaterEqual(events[0][0] - 100, config.VOLUME_LONG_PRESS_MS)
        gaps = [b[0] - a[0] for a, b in zip(events, events[1:])]
        self.assertTrue(all(g >= config.VOLUME_REPEAT_MS for g in gaps), gaps)
        self.release(config.BUTTON_MODE)
        self.assertEqual(self.poll_for(1750, 1900), [])             # no "mode" on release

    def test_back_long_press(self):
        self.press(config.BUTTON_BACK)
        names = [e for _t, e in self.poll_for(100, 1000)]
        self.assertIn("back_hold", names)

    def test_action_has_no_long_press(self):
        self.press(config.BUTTON_ACTION)
        names = [e for _t, e in self.poll_for(100, 2000)]
        self.assertEqual(names, ["action"])

    def test_press_just_below_the_limit_is_short(self):
        self.press(config.BUTTON_BACK)
        self.assertEqual(self.poll_for(100, 100 + config.VOLUME_LONG_PRESS_MS - 100), [])
        self.release(config.BUTTON_BACK)
        names = [e for _t, e in self.poll_for(100 + config.VOLUME_LONG_PRESS_MS - 50, 800)]
        self.assertEqual(names, ["back"])


class VolumeBarTests(unittest.TestCase):
    def test_bar_levels_and_position(self):
        face = FaceRenderer()
        for level, white in ((0, 0), (5, 1), (40, 4), (100, 10)):
            bars = face.volume_bar(level)
            self.assertEqual(len(bars), 10)
            self.assertEqual(sum(1 for b in bars if b["color"] == 0xFFFF), white, level)
            for b in bars:
                self.assertGreater(b["y"], 215)                     # below the face
                self.assertLessEqual(b["y"] + b["height"], 280)
                self.assertTrue(0 <= b["x"] and b["x"] + b["width"] <= 240)


class DisplayTests(unittest.TestCase):
    def make(self, partial):
        config.DISPLAY_PARTIAL = partial
        return ST7789()

    def tearDown(self):
        config.DISPLAY_PARTIAL = True

    def frames(self):
        face = FaceRenderer(config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT)
        emotions = ("neutral", "happy", "sad", "sleepy", "surprised", "angry")
        out = []
        for i, to in enumerate(emotions):
            frm = emotions[i - 1]
            for blend in (0.0, 0.4, 1.0):
                for frame in (1, 25, 79, 80):
                    commands = face.render(to, 0.2 + 0.15 * i, frame=frame,
                                           from_emotion=frm, blend=blend)
                    if frame in (25, 80):                      # volume bar on, then off again
                        commands = commands + face.volume_bar(10 * i)
                    out.append(commands)
        return out

    def test_every_face_draws_without_errors(self):
        d = self.make(True)
        for commands in self.frames():
            d.render(commands)

    def test_partial_update_equals_full_redraw(self):
        part, full = self.make(True), self.make(False)
        part_bytes = full_bytes = 0
        for commands in self.frames():
            part.render(commands)
            full.render(commands)
            part_bytes += part.last_bytes
            full_bytes += full.last_bytes
            self.assertEqual(part.buffer, full.buffer)
            # what really reached the (fake) glass equals the memory buffer
            self.assertEqual(part.spi.screen, part.buffer)
            self.assertEqual(full.spi.screen, full.buffer)
        self.assertLess(part_bytes, full_bytes * 0.8)

    def test_background_colour_change_forces_full_redraw(self):
        d = self.make(True)
        bg = lambda c: [{"type": "fill_rect", "x": 0, "y": 0, "width": 240,
                         "height": 280, "color": c}]
        d.render(bg(0x0000))
        d.render(bg(0xF800))
        self.assertEqual(d.last_bytes, 240 * 280 * 2)
        self.assertEqual(d.spi.screen, d.buffer)

    def test_colour_bytes_are_sent_high_byte_first(self):
        d = self.make(True)
        d.fill_rect(0, 0, 2, 1, 0xF800)                      # pure red
        self.assertEqual(bytes(d.buffer[0:4]), bytes((0xF8, 0x00, 0xF8, 0x00)))

    def test_black_frame_is_sent_before_backlight(self):
        d = self.make(True)
        self.assertEqual(Pin.levels[config.DISPLAY_BL], 1)
        self.assertEqual(d.spi.screen, bytearray(240 * 280 * 2))

    def test_empty_frame_after_content_erases_it(self):
        d = self.make(True)
        face = FaceRenderer()
        d.render(face.render("happy", 0.8))
        d.render([])
        self.assertEqual(d.buffer, bytearray(240 * 280 * 2))
        self.assertEqual(d.spi.screen, d.buffer)


class StopLoop(BaseException):
    pass


class MainLoopTest(unittest.TestCase):
    def test_robot_runs_reacts_to_button_and_beeps(self):
        import importlib
        saved = {n: getattr(time, n) for n in ("ticks_ms", "sleep_ms")}
        saved_period = config.MIC_SAMPLE_PERIOD_US
        config.MIC_SAMPLE_PERIOD_US = 0
        clock = {"t": 0}
        I2S.instances = []

        def fake_sleep(ms):
            clock["t"] += ms
            Pin.levels[config.BUTTON_ACTION] = 0 if 1000 <= clock["t"] < 1200 else 1
            Pin.levels[config.BUTTON_MODE] = 0 if 2000 <= clock["t"] < 3300 else 1
            if clock["t"] > 5500:
                raise StopLoop()

        time.ticks_ms = lambda: clock["t"]
        time.sleep_ms = fake_sleep
        out = io.StringIO()
        bar_levels = []
        original_bar = FaceRenderer.volume_bar

        def spy(face, level):
            bar_levels.append(level)
            return original_bar(face, level)

        try:
            import main
            importlib.reload(main)
            with mock.patch.object(FaceRenderer, "volume_bar", spy):
                with contextlib.redirect_stdout(out):
                    with self.assertRaises(StopLoop):
                        main.main()
        finally:
            time.ticks_ms = saved["ticks_ms"]
            time.sleep_ms = saved["sleep_ms"]
            config.MIC_SAMPLE_PERIOD_US = saved_period
            Pin.levels[config.BUTTON_ACTION] = 1
            Pin.levels[config.BUTTON_MODE] = 1

        text = out.getvalue()
        for ok in ("Display: OK", "Microphone: OK", "Speaker: OK", "Buttons: OK"):
            self.assertIn(ok, text)
        self.assertNotIn("ERROR", text)
        self.assertIn("emotion=happy", text)                  # ACTION button reaction
        self.assertTrue(any(any(w) for w in I2S.instances[0].writes))   # a beep was sent
        volumes = [int(v) for v in re.findall(r"vol=(\d+)", text)]
        self.assertEqual(volumes[0], config.SPEAKER_VOLUME)
        self.assertGreater(volumes[-1], config.SPEAKER_VOLUME)           # MODE held = louder
        self.assertLessEqual(volumes[-1], config.SPEAKER_VOLUME + 5 * 6)
        # the volume bar is shown after the first step and disappears again
        self.assertTrue(20 < len(bar_levels) < 50, len(bar_levels))
        self.assertGreater(bar_levels[0], config.SPEAKER_VOLUME)
        self.assertIn("render=", text)


if __name__ == "__main__":
    unittest.main()
