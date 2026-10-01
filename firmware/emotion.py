class EmotionController:
    """Hardware-independent emotion and state machine.

    The controller converts events into visible robot behaviour.
    Time is supplied by the caller, so this module stays easy to test
    on a PC and later on MicroPython.
    """

    EMOTIONS = (
        "neutral",
        "happy",
        "sad",
        "sleepy",
        "surprised",
        "angry",
    )

    STATES = (
        "idle",
        "listening",
        "thinking",
        "music",
        "sleeping",
    )

    EVENTS = (
        "boot",
        "button_action",
        "sound_music",
        "sound_laughter",
        "sound_speech",
        "sound_noise",
        "silence",
        "message_received",
        "ai_thinking",
        "sleep",
        "wake",
        "error",
    )

    def __init__(self):
        self.emotion = "neutral"
        self.intensity = 0.5
        self.state = "idle"
        self.expires_at = None

    def _set(self, emotion, state, intensity=0.5, duration_ms=None, now_ms=0):
        if emotion not in self.EMOTIONS:
            raise ValueError("Unknown emotion: {}".format(emotion))
        if state not in self.STATES:
            raise ValueError("Unknown state: {}".format(state))
        if not 0.0 <= intensity <= 1.0:
            raise ValueError("Intensity must be between 0.0 and 1.0")

        self.emotion = emotion
        self.state = state
        self.intensity = intensity

        if duration_ms is None:
            self.expires_at = None
        else:
            self.expires_at = now_ms + duration_ms

    def handle_event(self, event, now_ms=0):
        if event not in self.EVENTS:
            raise ValueError("Unknown event: {}".format(event))

        if event == "boot":
            self._set("neutral", "idle", 0.5)
        elif event == "button_action":
            self._set("happy", "idle", 0.8, 2500, now_ms)
        elif event == "sound_music":
            self._set("happy", "music", 0.8, 5000, now_ms)
        elif event == "sound_laughter":
            self._set("happy", "idle", 1.0, 3500, now_ms)
        elif event == "sound_speech":
            self._set("neutral", "listening", 0.7)
        elif event == "sound_noise":
            self._set("surprised", "idle", 0.9, 2000, now_ms)
        elif event == "silence":
            self._set("neutral", "idle", 0.4)
        elif event == "message_received":
            self._set("surprised", "idle", 0.9, 3000, now_ms)
        elif event == "ai_thinking":
            self._set("neutral", "thinking", 0.6)
        elif event == "sleep":
            self._set("sleepy", "sleeping", 0.7)
        elif event == "wake":
            self._set("happy", "idle", 0.6, 2000, now_ms)
        elif event == "error":
            self._set("sad", "idle", 0.8, 3000, now_ms)

        return self.status()

    def tick(self, now_ms):
        if self.expires_at is not None and now_ms >= self.expires_at:
            self._set("neutral", "idle", 0.4)
        return self.status()

    def set_emotion(self, emotion, intensity=0.5, duration_ms=None, now_ms=0):
        self._set(emotion, "idle", intensity, duration_ms, now_ms)
        return self.status()

    def status(self):
        return {
            "emotion": self.emotion,
            "intensity": self.intensity,
            "state": self.state,
            "expires_at": self.expires_at,
        }
