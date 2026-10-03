from robot import Robot
from emotion import EmotionController
from face import FaceRenderer


def main():
    robot = Robot()
    emotions = EmotionController()
    face = FaceRenderer()

    print("Pocket Robot V1")
    print("----------------")

    emotions.handle_event("boot")

    events = [
        ("button_action", 1000),
        ("sound_music", 4000),
        ("sound_speech", 10000),
        ("ai_thinking", 12000),
        ("message_received", 14000),
        ("silence", 18000),
    ]

    for event, now_ms in events:
        status = emotions.handle_event(event, now_ms)
        robot.set_mood(status["emotion"], status["intensity"])
        robot.set_state(status["state"])
        draw_commands = face.render(status["emotion"], status["intensity"], frame=now_ms // 100)
        print("{} -> {}".format(event, robot.status()))
        print("  draw commands:", len(draw_commands))


if __name__ == "__main__":
    main()