class FaceRenderer:
    """Convert robot emotions into hardware-independent drawing commands.

    The renderer does not know anything about ST7789 or a graphics library.
    It produces simple primitives (ellipse, line, arc, circle, text) that a
    display driver can later translate into real pixels.

    The current target is the 240x280 ST7789 display.
    """

    BACKGROUND = 0x0000
    FACE_COLOR = 0xFFFF

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

    def _eye(self, x, y, width, height, pupil_scale=0.35):
        return [
            self._command("fill_ellipse", x=x, y=y, width=width, height=height, color=self.FACE_COLOR),
            self._command(
                "fill_ellipse",
                x=int(x + width * 0.5 - width * pupil_scale * 0.5),
                y=int(y + height * 0.5 - height * pupil_scale * 0.5),
                width=int(width * pupil_scale),
                height=int(height * pupil_scale),
                color=self.BACKGROUND,
            ),
        ]

    def _closed_eye(self, x, y, width):
        return [self._command("arc", x=x, y=y, width=width, height=18, start=200, end=340, color=self.FACE_COLOR, thickness=4)]

    def _brow(self, x, y, width, angle):
        return [self._command("line", x1=x, y1=y, x2=x + width, y2=y + angle, color=self.FACE_COLOR, thickness=4)]

    def _mouth(self, emotion, intensity):
        mouth_x = self.cx
        mouth_y = int(self.height * 0.63)
        width = int(48 + 18 * intensity)

        if emotion == "happy":
            return [self._command("arc", x=mouth_x - width // 2, y=mouth_y - 10, width=width, height=34, start=20, end=160, color=self.FACE_COLOR, thickness=5)]

        if emotion == "sad":
            return [self._command("arc", x=mouth_x - width // 2, y=mouth_y - 2, width=width, height=34, start=200, end=340, color=self.FACE_COLOR, thickness=5)]

        if emotion == "surprised":
            size = int(24 + 12 * intensity)
            return [
                self._command("fill_ellipse", x=mouth_x - size // 2, y=mouth_y - size // 2, width=size, height=size + 4, color=self.FACE_COLOR),
                self._command("fill_ellipse", x=mouth_x - size // 4, y=mouth_y - size // 4, width=size // 2, height=size // 2, color=self.BACKGROUND),
            ]

        if emotion == "angry":
            return [self._command("line", x1=mouth_x - width // 2, y1=mouth_y, x2=mouth_x + width // 2, y2=mouth_y, color=self.FACE_COLOR, thickness=5)]

        if emotion == "sleepy":
            return [self._command("line", x1=mouth_x - width // 3, y1=mouth_y, x2=mouth_x + width // 3, y2=mouth_y, color=self.FACE_COLOR, thickness=4)]

        return [self._command("arc", x=mouth_x - width // 2, y=mouth_y - 5, width=width, height=24, start=25, end=155, color=self.FACE_COLOR, thickness=4)]

    def render(self, emotion="neutral", intensity=0.5, frame=0):
        """Return drawing commands for one animation frame."""
        if emotion not in ("neutral", "happy", "sad", "sleepy", "surprised", "angry"):
            raise ValueError("Unknown emotion: {}".format(emotion))
        if not 0.0 <= intensity <= 1.0:
            raise ValueError("Intensity must be between 0.0 and 1.0")

        commands = [self._command("fill_rect", x=0, y=0, width=self.width, height=self.height, color=self.BACKGROUND)]
        blink = frame % 40 in (0, 1)
        eye_width = int(42 + 10 * intensity)
        eye_height = int(48 + 18 * intensity)

        if emotion == "sleepy":
            commands.extend(self._closed_eye(self.left_eye_x - eye_width // 2, self.eye_y, eye_width))
            commands.extend(self._closed_eye(self.right_eye_x - eye_width // 2, self.eye_y, eye_width))
        elif blink:
            commands.extend(self._closed_eye(self.left_eye_x - eye_width // 2, self.eye_y + eye_height // 2, eye_width))
            commands.extend(self._closed_eye(self.right_eye_x - eye_width // 2, self.eye_y + eye_height // 2, eye_width))
        else:
            if emotion == "surprised":
                eye_width = int(50 + 16 * intensity)
                eye_height = int(58 + 20 * intensity)
            commands.extend(self._eye(self.left_eye_x - eye_width // 2, self.eye_y, eye_width, eye_height, pupil_scale=0.30))
            commands.extend(self._eye(self.right_eye_x - eye_width // 2, self.eye_y, eye_width, eye_height, pupil_scale=0.30))

        if emotion == "happy":
            commands.extend(self._brow(self.left_eye_x - eye_width // 2, self.eye_y - 14, eye_width, -8))
            commands.extend(self._brow(self.right_eye_x - eye_width // 2, self.eye_y - 6, eye_width, 8))
        elif emotion == "sad":
            commands.extend(self._brow(self.left_eye_x - eye_width // 2, self.eye_y - 8, eye_width, 10))
            commands.extend(self._brow(self.right_eye_x - eye_width // 2, self.eye_y + 2, eye_width, -10))
        elif emotion == "angry":
            commands.extend(self._brow(self.left_eye_x - eye_width // 2, self.eye_y - 4, eye_width, 12))
            commands.extend(self._brow(self.right_eye_x - eye_width // 2, self.eye_y + 8, eye_width, -12))

        commands.extend(self._mouth(emotion, intensity))
        return commands

    def frame_count(self):
        return 40