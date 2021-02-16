from contextlib import contextmanager
from io import StringIO

from conan.locks.backend import LockBackend
from conan.locks.backend_sqlite3 import LockBackendSqlite3Memory, LockBackendSqlite3Filesystem


class LocksManager:

    def __init__(self, backend: LockBackend):
        self._backend = backend

    @staticmethod
    def create(backend_id: str, **backend_kwargs):
        if backend_id == 'sqlite3':
            backend = LockBackendSqlite3Filesystem(**backend_kwargs)
            backend.create_table(if_not_exists=True)
            return LocksManager(backend)
        elif backend_id == 'memory':
            backend = LockBackendSqlite3Memory(**backend_kwargs)
            backend.create_table(if_not_exists=True)
            return LocksManager(backend)
        else:
            raise NotImplementedError(f'Backend {backend_id} for locks is not implemented')

    def dump(self, output: StringIO):
        self._backend.dump(output)

    def try_acquire(self, resource: str, blocking: bool, wait: bool):
        lock_id = None
        while not lock_id:
            try:
                lock_id = self._backend.try_acquire(resource, blocking)
            except Exception as e:
                if not wait:
                    raise
                # TODO: Implement wait mechanism, timeout,...
                import time
                time.sleep(0.1)
            else:
                return lock_id

    def release(self, lock_id: LockBackend.LockId):
        self._backend.release(backend_id=lock_id)

    @contextmanager
    def lock(self, resource: str, blocking: bool, wait: bool):
        lock_id = self.try_acquire(resource, blocking, wait)
        try:
            yield
        finally:
            self.release(lock_id)
