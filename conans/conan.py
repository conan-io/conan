import gc
import sys


def run():
    # No cyclic garbage collector in the "conan" command: almost all the objects it creates live
    # until the end (the graph), so the collector didn't free memory, but it traversed all of them
    # again every time they had grown by 25%, up to half of the time of a command with a large
    # graph. Disabled before importing Conan, which also skips the collections of the imports.
    # The installer enables it again while it installs the packages, for the garbage of the builds
    gc.disable()
    from conan.internal.graph import installer
    installer.ENABLE_GC_FOR_BUILDS = True
    from conan.cli.cli import main
    main(sys.argv[1:])


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    run()
