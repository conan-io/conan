import sys

from conans.client.command import main


def run():
    input("Attach the debugger and press a key")
    main(sys.argv[1:])


if __name__ == '__main__':
    run()
