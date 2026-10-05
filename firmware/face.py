"""Procedural animated face for the 240x280 ST7789 display."""

import math


class FaceRenderer:
    """Convert emotion state into simple display drawing commands.

    The renderer is hardware-independent. It describes the face; display.py
    converts these commands into pixels.
    """

    BACKGROUND = 0x0000
    FACE_COLOR = 0xFFFF

    PROFILES = {
        "neutral": {"eye": 1.00, "brow_l": 0, "brow_r": 0, "mouth": 0.00, "open": 0.00},
        "happy": {"eye": 1.00, "brow_l": -8, "brow_r": 8, "mouth": 1.00, "open": 0.00},
        "sad": {"eye": 0.88, "brow_l": 10, "brow_r": -10, "mouth": -0.80, "open": 0.00},
        "sleepy": {"eye": 0.18, "brow_l": 0, "brow_r": 0, "mouth": -0.05, "open": 0.00},
        "surprised": {"eye": 1.30, "brow_l": -6, "brow_r": 6, "mouth": 0.00, "open": 1.00},
        "angry": {"eye": 0.90, "brow_l": 13, "brow_r": -13, "mouth": -0.35, "open": 0.00},
    }

    def __init__(self, width=240, height=280):
        self.width = width
        self.height = height
        self.cx = width // 2
        self.eye_y = int(height * 0.38)
        self.left_eye_x = int(width * 0.30)
        self.right_eye_x = int(width * 0.70)

    def _command(self, kind, **kwargs):
        command = {"type": kind}
        command.update(kwargs)
        return command

    def _lerp(self, a, b, t):
        return a + (b - a) * t

    def _profile(self, from_emotion, to_emotion, blend):
        if from_emotion not in self.PROFILES:
            from_emotion = "neutral"
        if to_emotion not in self.PROFILES:
            to_emotion = "neutral"
        a = self.PROFILES[from_emotion]
        b = self.PROFILES[to_emotion]
        return {
            key: self._lerp(a[key], b[key], blend)
            for key in a
        }

    def _eye(self, x, y, width, height, pupil_scale=0.30):
        return [
            self._command("fill_ellipse", x=x, y=y, width=width, height=height, color=self.FACE_COLOR),
            self._command(
                "fill_ellipse",
                x=int(x + width * 0.5 - width * pupil_scale * 0.5),
                y=int(y + height * 0.5 - height * pupil_scale * 0.5),
                width=max(2, int(width * pupil_scale)),
                height=max(2, int(height * pupil_scale)),
                color=self.BACKGROUND,
            ),
        ]

    def _closed_eye(self, x, y, width):
        return [self._command("arc", x=x, y=y, width=width, height=18,
                              start=200, end=340, color=self.FACE_COLOR, thickness=4)]

    def _brow(self, x, y, width, angle):
        return [self._command("line", x1=x, y1=y, x2=x + width, y2=y + angle,
                              color=self.FACE_COLOR, thickness=4)]

    def _mouth(self, curve, opening, intensity):
        mouth_x = self.cx
        mouth_y = int(self.height * 0.63)
        width = int(48 + 18 * intensity)

        if opening > 0.35:
            size = int(20 + 18 * opening * intensity)
            return [
                self._command("fill_ellipse", x=mouth_x - size // 2,
                              y=mouth_y - size // 2, width=size,
                              height=size + 5, color=self.FACE_COLOR),
                self._command("fill_ellipse", x=mouth_x - size // 4,
                              y=mouth_y - size // 4, width=max(2, size // 2),
                              height=max(2, size // 2), color=self.BACKGROUND),
            ]

        # Curve > 0 = smile, curve < 0 = frown.
        if curve >= 0:
            start, end = 20, 160
            y = mouth_y - 10 - int(curve * 3)
        else:
            start, end = 200, 340
            y = mouth_y - 2 + int((-curve) * 3)

        height = int(24 + 10 * abs(curve))
        thickness = 4 + int(2 * intensity)
        return [self._command("arc", x=mouth_x - width // 2, y=y,
                              width=width, height=height, start=start, end=end,
                              color=self.FACE_COLOR, thickness=thickness)]

    def render(self, emotion="neutral", intensity=0.5, frame=0,
               from_emotion=None, blend=1.0):
        """Return drawing commands for one animation frame.

        from_emotion + blend allow the face geometry to morph smoothly from
        one emotion into another instead of switching instantly.
        """
        if emotion not in self.PROFILES:
            raise ValueError("Unknown emotion: {}".format(emotion))
        if not 0.0 <= intensity <= 1.0:
            raise ValueError("Intensity must be between 0.0 and 1.0")
        if from_emotion is None:
            from_emotion = emotion
        blend = max(0.0, min(1.0, blend))

        profile = self._profile(from_emotion, emotion, blend)
        commands = [self._command("fill_rect", x=0, y=0, width=self.width,
                                  height=self.height, color=self.BACKGROUND)]

        eye_width = int((42 + 10 * intensity) * (0.92 + 0.08 * profile["eye"]))
        eye_height = int((48 + 18 * intensity) * profile["eye"])
        eye_height = max(6, eye_height)

        # Blink is deterministic and does not allocate random state.
        blink = frame % 80 in (0, 1)
        if profile["eye"] < 0.30:
            commands.extend(self._closed_eye(self.left_eye_x - eye_width // 2,
                                             self.eye_y + eye_height // 2, eye_width))
            commands.extend(self._closed_eye(self.right_eye_x - eye_width // 2,
                                             self.eye_y + eye_height // 2, eye_width))
        elif blink:
            commands.extend(self._closed_eye(self.left_eye_x - eye_width // 2,
                                             self.eye_y + eye_height // 2, eye_width))
            commands.extend(self._closed_eye(self.right_eye_x - eye_width // 2,
                                             self.eye_y + eye_height // 2, eye_width))
        else:
            commands.extend(self._eye(self.left_eye_x - eye_width // 2,
                                      self.eye_y, eye_width, eye_height))
            commands.extend(self._eye(self.right_eye_x - eye_width // 2,
                                      self.eye_y, eye_width, eye_height))

        # Gentle eye motion makes the face feel alive without a camera.
        look = int(2 * math.sin(frame * 0.10))
        if not blink and profile["eye"] >= 0.30:
            # A tiny pair of black pixels is intentionally avoided here;
            # pupil motion is added later by a hardware-optimized renderer.
            pass

        brow_y = self.eye_y - 14
        commands.extend(self._brow(self.left_eye_x - eye_width // 2,
                                   brow_y, eye_width, int(profile["brow_l"])))
        commands.extend(self._brow(self.right_eye_x - eye_width // 2,
                                   brow_y, eye_width, int(profile["brow_r"])))

        commands.extend(self._mouth(profile["mouth"], profile["open"], intensity))
        return commands

    def frame_count(self):
        return 80
