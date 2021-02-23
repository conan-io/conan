import errno
import os
import sys
import time
from threading import Timer

from conan.locks.locks_manager import LocksManager

cache_database = f'{__file__}-locks.sqlite3'
writer_sentinel = f'{__file__}-writer'
reader_sentinel = f'{__file__}-reader'
resource = 'resource'
time_step = 1
time_reader_wait = time_step * 2


def write(msg: str, newline: bool = True):
    sys.stdout.write(msg)
    if newline:
        sys.stdout.write('\n')
    sys.stdout.flush()


def silentremove(filename):
    try:
        os.remove(filename)
    except OSError as e:  # this would be "except OSError, e:" before Python 2.6
        if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
            raise  # re-raise exception if a different error occurred


def run_writer():
    assert not os.path.exists(reader_sentinel)
    cache1 = LocksManager.create('sqlite3', filename=cache_database)
    with cache1.lock(resource, blocking=True, wait=False):
        # Create the writer file
        with open(writer_sentinel, 'w') as f:
            f.write('writing')
        # Wait for the reader file
        while not os.path.exists(reader_sentinel):
            write(f"WRITER: wait for reader file: {reader_sentinel}")
            time.sleep(time_step)


def run_reader():
    while not os.path.exists(writer_sentinel):
        write(f"READER: wait for writer file: {writer_sentinel}")
        time.sleep(time_step)

    cache2 = LocksManager.create('sqlite3', filename=cache_database)

    # Check we cannot enter a resource already locked by the writer (nor write, neither read)
    try:
        with cache2.lock(resource, blocking=True, wait=False):
            exit(-1)
    except Exception as e:
        assert str(e) == f"Resource '{resource}' is already blocked", f"Mismatch! It was '{e}'"

    try:
        with cache2.lock(resource, blocking=False, wait=False):
            exit(-1)
    except Exception as e:
        assert str(e) == f"Resource '{resource}' is blocked by a writer", f"Mismatch! It was '{e}'"

    # Check that we pass once the writer releases the resource
    t = Timer(time_reader_wait, lambda: open(reader_sentinel, 'w').close())
    t.start()
    with cache2.lock(resource, blocking=False, wait=True):
        write('READER: Entered resource after waiting for it')


if __name__ == '__main__':
    argument: str = sys.argv[1]
    if argument == 'writer':
        run_writer()
    else:
        try:
            run_reader()
        finally:
            # Ensure the writer finish regardless of what happens in the reader
            with open(reader_sentinel, 'w') as f:
                f.write('reader')
