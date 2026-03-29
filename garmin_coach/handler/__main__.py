from garmin_coach.handler import process_message


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--message", required=True)
    args = parser.parse_args()

    print(process_message(args.message))
