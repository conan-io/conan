from contextlib import contextmanager

from conan.locks.backend import LockBackend
from conan.locks.backend_sqlite3 import LockBackendSqlite3


class LocksManager:

    def __init__(self, backend: LockBackend):
        self._backend = backend

    @staticmethod
    def create(backend_id: str, **backend_kwargs):
        if backend_id == 'sqlite3':
            return LocksManager(LockBackendSqlite3(**backend_kwargs))
        elif backend_id == 'memory':
            return LocksManager(LockBackendSqlite3(':memory:'))
        else:
            raise NotImplementedError(f'Backend {backend_id} for locks is not implemented')

    def try_acquire(self, resource: str, blocking: bool, wait: bool):
        lock_id = None
        while not lock_id and wait:
            try:
                lock_id = self._backend.try_acquire(resource, blocking)
            except Exception:
                # TODO: Implement wait mechanism, timeout,...
                import time
                time.sleep(1)
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

    def get_lockable_resource(self, resource: str, blocking: bool, wait: bool) -> 'LockableResource':
        return LockableResource(manager=self, resource=resource, blocking=blocking, wait=wait)
