import pytest
from conan.locks.lockable_mixin import LockableMixin


class TestLockableMixin:

    def test_with_writers(self, lock_manager):
        resource = 'res'

        l1 = LockableMixin(lock_manager, resource)
        l2 = LockableMixin(lock_manager, resource)

        with l1.lock(blocking=True, wait=False):
            with pytest.raises(Exception) as excinfo:
                with l2.lock(blocking=True, wait=False):
                    pass
            assert "Resource 'res' is already blocked" == str(excinfo.value)

        with l2.lock(blocking=True, wait=False):
            with pytest.raises(Exception) as excinfo:
                with l1.lock(blocking=True, wait=False):
                    pass
            assert "Resource 'res' is already blocked" == str(excinfo.value)

    def test_readers(self, lock_manager):
        resource = 'res'

        l1 = LockableMixin(lock_manager, resource)
        l2 = LockableMixin(lock_manager, resource)

        with l1.lock(blocking=False, wait=False):
            with l2.lock(blocking=False, wait=False):
                pass

        with l2.lock(blocking=False, wait=False):
            with l1.lock(blocking=False, wait=False):
                pass
