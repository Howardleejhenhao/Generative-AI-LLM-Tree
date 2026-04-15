import sys
import time


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        time.sleep(60)


if __name__ == "__main__":
    main()
