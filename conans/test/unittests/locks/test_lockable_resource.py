import pytest

from locks.locks_manager import LocksManager


class TestLockableResource:

    def test_block(self):
        manager = LocksManager.create('memory')
        resource = 'res'

        l1 = manager.get_lockable_resource(resource, blocking=True, wait=False)
        l2 = manager.get_lockable_resource(resource, blocking=True, wait=False)

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
