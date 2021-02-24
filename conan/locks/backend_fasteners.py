import logging
import os
import threading
from contextlib import contextmanager
from io import StringIO

import fasteners

from conan.locks.backend import LockBackend
from conan.locks.exceptions import AlreadyLockedException

log = logging.getLogger(__name__)


class RWLock(object):
    def __init__(self, resource: str, interprocess_lock: str):
        self.w_lock = threading.Lock()
        self.num_r_lock = threading.Lock()
        self.num_r = 0
        self._resource = resource
        self._interprocess_lock = fasteners.InterProcessReaderWriterLock(interprocess_lock)

    def r_acquire(self):
        self.num_r_lock.acquire()
        try:
            if self.num_r == 0:
                ret = self.w_lock.acquire(blocking=False)
                if not ret:
                    raise AlreadyLockedException(self._resource, by_writer=True)

                if not self._interprocess_lock.acquire_read_lock(blocking=False):
                    self.w_lock.release()
                    raise AlreadyLockedException(self._resource, by_writer=True)

            self.num_r += 1
        finally:
            self.num_r_lock.release()

    def r_release(self):
        assert self.num_r > 0
        self.num_r_lock.acquire()
        try:
            self.num_r -= 1
            if self.num_r == 0:
                self._interprocess_lock.release_read_lock()
                self.w_lock.release()
        finally:
            self.num_r_lock.release()

    def w_acquire(self):
        if not self.w_lock.acquire(blocking=False):
            raise AlreadyLockedException(self._resource)

        if not self._interprocess_lock.acquire_write_lock(blocking=False):
            self.w_lock.release()
            raise AlreadyLockedException(self._resource)

    def w_release(self):
        self.w_lock.release()
        self._interprocess_lock.release_write_lock()


class LockBackendFasteners(LockBackend):
    _threading_locks_guard = threading.Lock()
    _threading_locks = {}

    def __init__(self, locks_directory: str):
        self._locks_directory = locks_directory

    def dump(self, output: StringIO):
        with self._locks_guard():
            for key, value in self._threading_locks.items():
                _, _, blocking = value
                output.write(f'{key}: {"blocking" if blocking else "non-blocking"}')

    @classmethod
    @contextmanager
    def _locks_guard(cls):
        cls._threading_locks_guard.acquire(blocking=True)
        try:
            yield
        finally:
            cls._threading_locks_guard.release()

    def _get_locks(self, resource: str) -> RWLock:
        locks = self._threading_locks.get(resource)
        if not locks:
            # lock_threading = fasteners.ReaderWriterLock()
            interprocess_lock = os.path.join(self._locks_directory, f'{resource}.lock')
            lock_threading = RWLock(resource, interprocess_lock)
            locks = lock_threading
            self._threading_locks[resource] = locks
        return locks

    @contextmanager
    def lock(self, resource: str, blocking: bool):
        log.error("lock(resource='%s', blocking='%s')", resource, blocking)
        with self._locks_guard():
            lock_threading = self._get_locks(resource)

        lock_threading.w_acquire() if blocking else lock_threading.r_acquire()
        try:
            yield
        finally:
            lock_threading.w_release() if blocking else lock_threading.r_release()
