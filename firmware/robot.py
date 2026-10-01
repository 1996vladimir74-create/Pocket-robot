class Robot:
    """Core state and behaviour of Pocket Robot.

    No hardware dependencies: display, audio, buttons and Wi-Fi
    will use this class instead of containing application logic.
    """

    VALID_MOODS = (
        "neutral",
        "happy",
        "sad",
        "sleepy",
        "surprised",
        "angry",
    )

    def __init__(self):
        self.mood = "neutral"
        self.volume = 50
        self.temperature = None
        self.wifi = False
        self.message = None

    def set_mood(self, mood):
        if mood not in self.VALID_MOODS:
            raise ValueError("Unknown mood: {}".format(mood))
        self.mood = mood

    def set_volume(self, volume):
        if not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")
        self.volume = volume

    def set_temperature(self, temperature):
        self.temperature = temperature

    def set_wifi(self, connected):
        self.wifi = bool(connected)

    def set_message(self, message):
        self.message = message

    def clear_message(self):
        self.message = None

    def status(self):
        return {
            "mood": self.mood,
            "volume": self.volume,
            "temperature": self.temperature,
            "wifi": self.wifi,
            "message": self.message,
        }
