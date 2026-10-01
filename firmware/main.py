from robot import Robot


def main():
    robot = Robot()

    print("Pocket Robot V1")
    print("----------------")
    print("Initial status:")
    print(robot.status())

    robot.set_mood("happy")
    robot.set_volume(70)
    robot.set_wifi(True)
    robot.set_temperature(22)
    robot.set_message("Hello! Hardware is coming.")

    print("\nAfter commands:")
    print(robot.status())


if __name__ == "__main__":
    main()
