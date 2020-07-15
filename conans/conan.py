import sys
import os

if os.getenv("CONAN_V2_CLI"):
    from conans.cli.cli import main
else:
    from conans.client.command import main


def run():
    main(sys.argv[1:])


if __name__ == '__main__':
    run()
