from contextlib import contextmanager

import fasteners


@contextmanager
def simple_lock(lock_path):
    lock = fasteners.InterProcessLock(lock_path)
    with lock:
        yield


@contextmanager
def read_lock(lock_path):
    rw_lock = fasteners.InterProcessReaderWriterLock(lock_path)
    with rw_lock.read_lock():
        yield


@contextmanager
def write_lock(lock_path):
    rw_lock = fasteners.InterProcessReaderWriterLock(lock_path)
    with rw_lock.write_lock():
        yield
