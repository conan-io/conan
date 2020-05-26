import os
import sys

from conans.client.command import main
from conans.cli.command import main


def run():
    if os.getenv("CONAN_V2_CLI"):
        main(sys.argv[1:])
    else:
        main(sys.argv[1:])


if __name__ == '__main__':
    run()
