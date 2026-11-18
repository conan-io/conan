import gc
import sys


def run():
    # No cyclic garbage collector in the "conan" command, see conan/internal/graph/graph_gc.py.
    # Disabled before importing Conan, which also skips the collections of the imports
    gc.disable()
    from conan.internal.graph import graph_gc
    graph_gc.CLI_DISABLED_GC = True
    from conan.cli.cli import main
    main(sys.argv[1:])


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    run()
