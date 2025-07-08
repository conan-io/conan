import sys
import multiprocessing
multiprocessing.freeze_support()
from conan.cli.cli import main


def run():
    main(sys.argv[1:])


if __name__ == '__main__':
    run()
