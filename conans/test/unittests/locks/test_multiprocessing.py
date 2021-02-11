# Test locks using 'multiprocessing' library
# TODO: Not sure if this is unittesting
import multiprocessing
from multiprocessing import Process, Manager

import pytest

from conan.locks.lockable_mixin import LockableMixin


def one_which_locks(c1, c2, manager, resource_id, return_dict):
    lock_mixin = LockableMixin(manager=manager, resource=resource_id)
    with lock_mixin.lock(blocking=True, wait=False):
        with c2:
            c2.notify_all()
        with c1:
            c1.wait()
    return_dict['one_which_locks'] = True


def one_which_raises(c1, manager, resource_id, return_dict):
    lock_mixin = LockableMixin(manager=manager, resource=resource_id)
    try:
        with lock_mixin.lock(blocking=True, wait=False):
            manager.dump()
    except Exception as e:
        assert "Resource 'whatever' is already blocked" == str(e)
        return_dict['one_which_raises'] = True
    finally:
        with c1:
            c1.notify_all()


def test_backend_memory(lock_manager_memory):
    resource_id = 'whatever'
    p = Process(target=one_which_locks, args=(None, lock_manager_memory, resource_id))
    with pytest.raises(Exception) as excinfo:
        p.start()
    assert "A memory Sqlite3 database is not pickable" == str(excinfo.value)


def test_backend_filename(lock_manager_sqlite3):
    multiprocessing_manager = Manager()
    return_dict = multiprocessing_manager.dict()
    c1 = multiprocessing.Condition()
    c2 = multiprocessing.Condition()

    resource_id = 'whatever'

    p1 = Process(target=one_which_locks,
                 args=(c1, c2, lock_manager_sqlite3, resource_id, return_dict))
    p1.start()

    with c2:
        c2.wait()

    p2 = Process(target=one_which_raises, args=(c1, lock_manager_sqlite3, resource_id, return_dict))
    p2.start()

    p2.join()
    p1.join()

    assert return_dict['one_which_raises']
    assert return_dict['one_which_locks']
