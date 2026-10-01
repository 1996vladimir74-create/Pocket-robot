class Robot:
    """Core state and behaviour of Pocket Robot.

    Hardware-independent application logic. Hardware drivers will use
    this class instead of containing application logic themselves.
    """

    VALID_MOODS = (
        "neutral",
        "happy",
        "sad",
        "sleepy",
        "surprised",
        "angry",
    )

    VALID_STATES = (
        "idle",
        "listening",
        "thinking",
        "music",
        "sleeping",
    )

    def __init__(self):
        self.mood = "neutral"
        self.intensity = 0.5
        self.state = "idle"
        self.volume = 50
        self.temperature = None
        self.wifi = False
        self.message = None

    def set_mood(self, mood, intensity=0.5):
        if mood not in self.VALID_MOODS:
            raise ValueError("Unknown mood: {}".format(mood))
        if not 0.0 <= intensity <= 1.0:
            raise ValueError("Intensity must be between 0.0 and 1.0")
        self.mood = mood
        self.intensity = intensity

    def set_state(self, state):
        if state not in self.VALID_STATES:
            raise ValueError("Unknown state: {}".format(state))
        self.state = state

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
            "intensity": self.intensity,
            "state": self.state,
            "volume": self.volume,
            "temperature": self.temperature,
            "wifi": self.wifi,
            "message": self.message,
        }
