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

    def volume_bar(self, level):
        """Ten rising bars near the bottom edge for a volume of 0..100 %.

        Returned as drawing commands to append to the face. The face never
        reaches below y=210, so the bars do not overlap it.
        """
        filled = (int(level) + 5) // 10
        base = self.height - 12
        x0 = self.cx - 80
        commands = []
        for i in range(10):
            h = 6 + i * 2
            color = self.FACE_COLOR if i < filled else 0x4208
            commands.append(self._command(
                "fill_rect", x=x0 + i * 16, y=base - h, width=12, height=h, color=color))
        return commands

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

    def _eye(self, x, y, width, height, pupil_scale=0.30, look=0):
        return [
            self._command("fill_ellipse", x=x, y=y, width=width, height=height, color=self.FACE_COLOR),
            self._command(
                "fill_ellipse",
                x=int(x + width * 0.5 - width * pupil_scale * 0.5) + look,
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
        # Gentle pupil motion makes the face feel alive without a camera.
        look = int(4 * math.sin(frame * 0.06))
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
                                      self.eye_y, eye_width, eye_height,
                                      look=look))
            commands.extend(self._eye(self.right_eye_x - eye_width // 2,
                                      self.eye_y, eye_width, eye_height,
                                      look=look))

        brow_y = self.eye_y - 14
        commands.extend(self._brow(self.left_eye_x - eye_width // 2,
                                   brow_y, eye_width, int(profile["brow_l"])))
        commands.extend(self._brow(self.right_eye_x - eye_width // 2,
                                   brow_y, eye_width, int(profile["brow_r"])))

        commands.extend(self._mouth(profile["mouth"], profile["open"], intensity))
        return commands

    def message_screen(self, message):
        """Render a short ASCII notification using MicroPython's built-in font."""
        translit = {
            "А":"A","Б":"B","В":"V","Г":"G","Д":"D","Е":"E","Ё":"Yo","Ж":"Zh",
            "З":"Z","И":"I","Й":"Y","К":"K","Л":"L","М":"M","Н":"N","О":"O",
            "П":"P","Р":"R","С":"S","Т":"T","У":"U","Ф":"F","Х":"Kh","Ц":"Ts",
            "Ч":"Ch","Ш":"Sh","Щ":"Shch","Ъ":"","Ы":"Y","Ь":"","Э":"E","Ю":"Yu","Я":"Ya",
            "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh",
            "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
            "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts",
            "ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
        }
        raw = str(message).replace("\\n", " ")
        text = "".join(translit.get(ch, ch) for ch in raw)
        text = " ".join(text.encode("ascii", "replace").decode().split())[:120]
        lines = []
        while text and len(lines) < 5:
            if len(text) <= 22:
                lines.append(text)
                break
            cut = text.rfind(" ", 0, 23)
            if cut < 1:
                cut = 22
            lines.append(text[:cut])
            text = text[cut:].strip()
        commands = [
            self._command("fill_rect", x=0, y=0, width=self.width,
                          height=self.height, color=self.BACKGROUND),
            self._command("line", x1=12, y1=12, x2=self.width - 12, y2=12,
                          color=self.FACE_COLOR, thickness=2),
            self._command("text", text="NEW MESSAGE", x=18, y=28,
                          color=self.FACE_COLOR),
        ]
        for i, line in enumerate(lines):
            commands.append(self._command("text", text=line, x=12,
                                          y=76 + i * 24, color=self.FACE_COLOR))
        commands.append(self._command("text", text="POCKET ROBOT", x=18, y=245,
                                      color=0x7BEF))
        return commands


    def weather_screen(self, weather):
        """Render current weather values supplied by the server."""
        temp = weather.get("temperature_c")
        feels = weather.get("feels_like_c")
        wind = weather.get("wind_kmh")
        humidity = weather.get("humidity_percent")
        def fmt(value, suffix):
            return "--" if value is None else "{}{}".format(round(value), suffix)
        lines = [
            "TEMP  " + fmt(temp, " C"),
            "FEELS " + fmt(feels, " C"),
            "WIND  " + fmt(wind, " km/h"),
            "HUMID " + fmt(humidity, " %"),
        ]
        commands = [
            self._command("fill_rect", x=0, y=0, width=self.width, height=self.height, color=self.BACKGROUND),
            self._command("text", text="WEATHER", x=18, y=28, color=self.FACE_COLOR),
            self._command("line", x1=12, y1=50, x2=self.width-12, y2=50, color=self.FACE_COLOR, thickness=2),
        ]
        for i, line in enumerate(lines):
            commands.append(self._command("text", text=line, x=18, y=82+i*32, color=self.FACE_COLOR))
        commands.append(self._command("text", text="OPEN-METEO", x=18, y=245, color=0x7BEF))
        return commands

    def frame_count(self):
        return 80
