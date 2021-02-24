import pytest

from conan.locks.locks_manager import LocksManager


class TestLocksManager:
    def test_plain_inside_context(self, lock_manager: LocksManager):
        resource = 'res'
        with lock_manager.lock(resource, blocking=True, wait=True):
            with pytest.raises(Exception) as excinfo:
                with lock_manager.lock(resource, blocking=False, wait=False):
                    pass
            assert "Resource 'res' is already blocked by a writer" == str(excinfo.value)

        with lock_manager.lock(resource, blocking=False, wait=False):
            pass

    def test_contextmanager_after_plain(self, lock_manager: LocksManager):
        lock_manager = LocksManager.create('memory')
        resource = 'res'

        with lock_manager.lock(resource, blocking=False, wait=True):
            with pytest.raises(Exception) as excinfo:
                with lock_manager.lock(resource, blocking=True, wait=False):
                    pass
            assert "Resource 'res' is already blocked" == str(excinfo.value)
