# Test locks using 'multiprocessing' library
# TODO: Not sure if this is unittesting
import sqlite3
import threading

import pytest

from conan.locks.backend_sqlite3 import LockBackendSqlite3
from conan.locks.lockable_mixin import LockableMixin
from conan.locks.locks_manager import LocksManager


def one_that_locks(c1, c2, manager, resource_id, return_dict):
    lock_mixin = LockableMixin(manager=manager, resource=resource_id)
    with lock_mixin.lock(blocking=True, wait=False):
        with c2:
            c2.notify_all()
        with c1:
            c1.wait()
    return_dict['one_which_locks'] = True


def one_that_raises(c1, manager, resource_id, return_dict):
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


def test_lock_mechanism(lock_manager: LocksManager):
    return_dict = dict()
    c1 = threading.Condition()
    c2 = threading.Condition()

    resource_id = 'whatever'

    p1 = threading.Thread(target=one_that_locks,
                          args=(c1, c2, lock_manager, resource_id, return_dict))
    p1.start()

    with c2:
        c2.wait()

    p2 = threading.Thread(target=one_that_raises, args=(c1, lock_manager, resource_id, return_dict))
    p2.start()

    p2.join()
    p1.join()

    assert return_dict['one_which_raises']
    assert return_dict['one_which_locks']


def test_underlying_sqlite(lock_backend_sqlite3: LockBackendSqlite3):
    """ Test that the sqlite3 database is locked while we are negotiating the locks """
    with lock_backend_sqlite3.connect() as _:
        with pytest.raises(sqlite3.OperationalError) as excinfo:
            with lock_backend_sqlite3.connect() as _:
                pass
        assert str(excinfo.value) in ["database schema is locked: main",  # Output with memory
                                      "database is locked"]  # Filesystem DB
