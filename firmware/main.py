from robot import Robot
from emotion import EmotionController


def main():
    robot = Robot()
    emotions = EmotionController()

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
        print("{} -> {}".format(event, robot.status()))


if __name__ == "__main__":
    main()
