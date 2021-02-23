import errno
import os
import sys
import time

from conan.locks.backend_sqlite3 import LockBackendSqlite3Filesystem

cache_database = f'{__file__}-locks.sqlite3'
writer_sentinel = f'{__file__}-writer'
reader_sentinel = f'{__file__}-reader'
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
    cache1 = LockBackendSqlite3Filesystem(filename=cache_database)
    with cache1.connect() as _:
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

    cache2 = LockBackendSqlite3Filesystem(filename=cache_database)

    # Check we cannot enter a resource already locked by the writer (nor write, neither read)
    try:
        with cache2.connect() as _:
            exit(-1)
    except Exception as e:
        assert str(e) == f"cannot rollback - no transaction is active"

    open(reader_sentinel, 'w').close()


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
