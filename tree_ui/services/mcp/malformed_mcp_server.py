import sys

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        # Just return garbage
        sys.stdout.write("this is not json\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
