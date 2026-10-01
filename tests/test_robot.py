import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE_DIR = os.path.join(PROJECT_ROOT, "firmware")

if FIRMWARE_DIR not in sys.path:
    sys.path.insert(0, FIRMWARE_DIR)

from robot import Robot


class TestRobot(unittest.TestCase):

    def setUp(self):
        self.robot = Robot()

    def test_initial_state(self):
        self.assertEqual(self.robot.mood, "neutral")
        self.assertEqual(self.robot.volume, 50)
        self.assertIsNone(self.robot.temperature)
        self.assertFalse(self.robot.wifi)
        self.assertIsNone(self.robot.message)

    def test_set_mood(self):
        self.robot.set_mood("happy")
        self.assertEqual(self.robot.mood, "happy")

    def test_invalid_mood(self):
        with self.assertRaises(ValueError):
            self.robot.set_mood("unknown")

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
        self.robot.set_mood("surprised")
        self.robot.set_volume(80)
        self.robot.set_wifi(True)
        self.robot.set_temperature(23.5)
        self.robot.set_message("Hi")

        self.assertEqual(
            self.robot.status(),
            {
                "mood": "surprised",
                "volume": 80,
                "temperature": 23.5,
                "wifi": True,
                "message": "Hi",
            },
        )


if __name__ == "__main__":
    unittest.main()
