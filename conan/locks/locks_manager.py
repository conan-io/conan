from contextlib import contextmanager

from conan.locks.backend import LockBackend
from conan.locks.backend_sqlite3 import LockBackendSqlite3
from conan.locks.lockable_resource import LockableResource


class LocksManager:

    def __init__(self, backend: LockBackend):
        self._backend = backend

    @staticmethod
    def create(backend_id: str, **backend_kwargs):
        if backend_id == 'sqlite3':
            backend = LockBackendSqlite3(**backend_kwargs)
            backend.create_table(if_not_exists=True)
            return LocksManager(backend)
        elif backend_id == 'memory':
            backend = LockBackendSqlite3(':memory:')
            backend.create_table(if_not_exists=True)
            return LocksManager(backend)
        else:
            raise NotImplementedError(f'Backend {backend_id} for locks is not implemented')

    def try_acquire(self, resource: str, blocking: bool, wait: bool):
        lock_id = None
        while not lock_id:
            try:
                lock_id = self._backend.try_acquire(resource, blocking)
            except Exception as e:
                if not wait:
                    raise
                # TODO: Implement wait mechanism, timeout,...
                print(e)
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

    def get_lockable_resource(self, resource: str, blocking: bool, wait: bool) -> LockableResource:
        return LockableResource(manager=self, resource=resource, blocking=blocking, wait=wait)
