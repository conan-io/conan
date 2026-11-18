import gc
import sys


def run():
    # No cyclic garbage collector in the "conan" command: almost all the objects it creates live
    # until the end (the graph), so the collector didn't free memory, but it traversed all of them
    # again every time they had grown by 25%, up to half of the time of a command with a large
    # graph. Disabled before importing Conan, which also skips the collections of the imports
    gc.disable()
    from conan.cli.cli import main
    try:
        main(sys.argv[1:])
    finally:
        # The interpreter shutdown runs a last collection even with the collector disabled, that
        # would traverse all the objects again, but it skips the frozen ones
        gc.freeze()


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    run()
