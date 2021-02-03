from conan.locks.locks_manager import LocksManager
import pytest


class TestLocksManagerMemoryBackend:
    backend = 'memory'

    def test_plain_inside_context(self):
        manager = LocksManager.create(self.backend)
        resource = 'res'
        with manager.lock(resource, blocking=True, wait=True):
            with pytest.raises(Exception) as excinfo:
                manager.try_acquire(resource, blocking=False, wait=False)
            assert "Resource 'res' is blocked by a writer" == str(excinfo.value)

        lock_id = manager.try_acquire(resource, blocking=False, wait=False)
        manager.release(lock_id)

    def test_contextmanager_after_plain(self):
        manager = LocksManager.create(self.backend)
        resource = 'res'

        lock_id = manager.try_acquire(resource, blocking=False, wait=True)
        with pytest.raises(Exception) as excinfo:
            with manager.lock(resource, blocking=True, wait=False):
                pass
        assert "Resource 'res' is already blocked" == str(excinfo.value)
        manager.release(lock_id)


# TODO: Implement basic test with SQlite3 backend

