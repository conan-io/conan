from conan.locks.locks_manager import LocksManager
import pytest


class TestLocksManager:
    def test_plain_inside_context(self, lock_manager):
        resource = 'res'
        with lock_manager.lock(resource, blocking=True, wait=True):
            with pytest.raises(Exception) as excinfo:
                lock_manager.try_acquire(resource, blocking=False, wait=False)
            assert "Resource 'res' is blocked by a writer" == str(excinfo.value)

        lock_id = lock_manager.try_acquire(resource, blocking=False, wait=False)
        lock_manager.release(lock_id)

    def test_contextmanager_after_plain(self, lock_manager):
        lock_manager = LocksManager.create('memory')
        resource = 'res'

        lock_id = lock_manager.try_acquire(resource, blocking=False, wait=True)
        with pytest.raises(Exception) as excinfo:
            with lock_manager.lock(resource, blocking=True, wait=False):
                pass
        assert "Resource 'res' is already blocked" == str(excinfo.value)
        lock_manager.release(lock_id)
