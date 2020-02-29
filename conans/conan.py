import sys

from conans.client.command import main


def run():
    main(sys.argv[1:])


if __name__ == '__main__':
    run()
