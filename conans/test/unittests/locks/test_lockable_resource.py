import pytest


class TestLockableResource:

    def test_with_writers(self, lock_manager):
        resource = 'res'

        l1 = lock_manager.get_lockable_resource(resource, blocking=True, wait=False)
        l2 = lock_manager.get_lockable_resource(resource, blocking=True, wait=False)

        with l1:
            with pytest.raises(Exception) as excinfo:
                with l2:
                    pass
            assert "Resource 'res' is already blocked" == str(excinfo.value)

        with l2:
            with pytest.raises(Exception) as excinfo:
                with l1:
                    pass
            assert "Resource 'res' is already blocked" == str(excinfo.value)

    def test_readers(self, lock_manager):
        resource = 'res'

        l1 = lock_manager.get_lockable_resource(resource, blocking=False, wait=False)
        l2 = lock_manager.get_lockable_resource(resource, blocking=False, wait=False)

        with l1:
            with l2:
                pass

        with l2:
            with l1:
                pass
