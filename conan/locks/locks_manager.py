from contextlib import contextmanager
from io import StringIO

from conan.locks.backend_fasteners import FastenersLock
from conan.locks.exceptions import AlreadyLockedException


class LocksManager:

    def __init__(self, locks_directory: str):
        self._locks = FastenersLock(locks_directory)

    def dump(self, output: StringIO):
        self._locks.dump(output)

    @contextmanager
    def lock(self, resource: str, blocking: bool, wait: bool):
        lock_acquired = False
        while not lock_acquired:
            try:
                with self._locks.lock(resource, blocking):
                    yield
            except AlreadyLockedException:
                if not wait:
                    raise
                # TODO: Implement wait mechanism, timeout,...
                import time
                time.sleep(0.1)
            else:
                lock_acquired = True
