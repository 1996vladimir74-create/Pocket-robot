import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE_DIR = os.path.join(PROJECT_ROOT, "firmware")
if FIRMWARE_DIR not in sys.path:
    sys.path.insert(0, FIRMWARE_DIR)

from robot import Robot
from emotion import EmotionController
from face import FaceRenderer

class TestRobot(unittest.TestCase):
    def setUp(self):
        self.robot = Robot()

    def test_initial_state(self):
        self.assertEqual(self.robot.mood, "neutral")
        self.assertEqual(self.robot.intensity, 0.5)
        self.assertEqual(self.robot.state, "idle")
        self.assertEqual(self.robot.volume, 50)
        self.assertIsNone(self.robot.temperature)
        self.assertFalse(self.robot.wifi)
        self.assertIsNone(self.robot.message)

    def test_set_mood(self):
        self.robot.set_mood("happy", 0.8)
        self.assertEqual(self.robot.mood, "happy")
        self.assertEqual(self.robot.intensity, 0.8)

    def test_invalid_mood(self):
        with self.assertRaises(ValueError):
            self.robot.set_mood("unknown")

    def test_invalid_intensity(self):
        with self.assertRaises(ValueError):
            self.robot.set_mood("happy", 1.1)

    def test_state(self):
        self.robot.set_state("thinking")
        self.assertEqual(self.robot.state, "thinking")

    def test_volume_range(self):
        self.robot.set_volume(0)
        self.robot.set_volume(100)
        with self.assertRaises(ValueError):
            self.robot.set_volume(101)
        with self.assertRaises(ValueError):
            self.robot.set_volume(-1)

    def test_message(self):
        self.robot.set_message("Test message")
        self.assertEqual(self.robot.message, "Test message")
        self.robot.clear_message()
        self.assertIsNone(self.robot.message)

    def test_status(self):
        self.robot.set_mood("surprised", 0.9)
        self.robot.set_state("listening")
        self.robot.set_volume(80)
        self.robot.set_wifi(True)
        self.robot.set_temperature(23.5)
        self.robot.set_message("Hi")
        self.assertEqual(self.robot.status(), {"mood": "surprised", "intensity": 0.9, "state": "listening", "volume": 80, "temperature": 23.5, "wifi": True, "message": "Hi"})

class TestEmotionController(unittest.TestCase):
    def setUp(self):
        self.emotion = EmotionController()

    def test_boot(self):
        self.emotion.handle_event("boot")
        self.assertEqual(self.emotion.emotion, "neutral")
        self.assertEqual(self.emotion.state, "idle")

    def test_music(self):
        self.emotion.handle_event("sound_music", now_ms=1000)
        self.assertEqual(self.emotion.emotion, "happy")
        self.assertEqual(self.emotion.state, "music")
        self.assertEqual(self.emotion.intensity, 0.8)
        self.assertEqual(self.emotion.expires_at, 6000)

    def test_speech(self):
        self.emotion.handle_event("sound_speech")
        self.assertEqual(self.emotion.emotion, "neutral")
        self.assertEqual(self.emotion.state, "listening")

    def test_message(self):
        self.emotion.handle_event("message_received", now_ms=1000)
        self.assertEqual(self.emotion.emotion, "surprised")
        self.assertEqual(self.emotion.expires_at, 4000)

    def test_temporary_emotion_expires(self):
        self.emotion.handle_event("button_action", now_ms=1000)
        self.emotion.tick(2000)
        self.assertEqual(self.emotion.emotion, "happy")
        self.emotion.tick(3500)
        self.assertEqual(self.emotion.emotion, "neutral")
        self.assertEqual(self.emotion.state, "idle")

    def test_sleep_and_wake(self):
        self.emotion.handle_event("sleep")
        self.assertEqual(self.emotion.emotion, "sleepy")
        self.assertEqual(self.emotion.state, "sleeping")
        self.emotion.handle_event("wake", now_ms=1000)
        self.assertEqual(self.emotion.emotion, "happy")
        self.assertEqual(self.emotion.state, "idle")

class TestFaceRenderer(unittest.TestCase):
    def setUp(self):
        self.face = FaceRenderer()

    def test_default_geometry(self):
        self.assertEqual(self.face.width, 240)
        self.assertEqual(self.face.height, 280)
        self.assertGreater(len(self.face.render("neutral", 0.5)), 0)

    def test_all_emotions_render(self):
        for emotion in EmotionController.EMOTIONS:
            commands = self.face.render(emotion, 0.5)
            self.assertGreater(len(commands), 0)
            self.assertEqual(commands[0]["type"], "fill_rect")

    def test_intensity_changes_geometry(self):
        normal = self.face.render("happy", 0.2)
        strong = self.face.render("happy", 1.0)
        self.assertNotEqual(normal, strong)

    def test_animation_frame_changes_output(self):
        open_eyes = self.face.render("neutral", 0.5, frame=10)
        blink = self.face.render("neutral", 0.5, frame=0)
        self.assertNotEqual(open_eyes, blink)

    def test_invalid_emotion(self):
        with self.assertRaises(ValueError):
            self.face.render("unknown", 0.5)

    def test_invalid_intensity(self):
        with self.assertRaises(ValueError):
            self.face.render("happy", 1.1)

if __name__ == "__main__":
    unittest.main()