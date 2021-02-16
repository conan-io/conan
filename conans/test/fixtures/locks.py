import os
import tempfile

import pytest

from conan.locks.backend_sqlite3 import LockBackendSqlite3Memory, LockBackendSqlite3Filesystem
from conan.locks.locks_manager import LocksManager


@pytest.fixture
def lock_backend_sqlite3_memory():
    return LockBackendSqlite3Memory()


@pytest.fixture
def lock_backend_sqlite3_filesystem():
    with tempfile.TemporaryDirectory() as tmpdirname:
        filename = os.path.join(tmpdirname, 'database.sqlite3')
        db = LockBackendSqlite3Filesystem(filename=filename)
        yield db


@pytest.fixture(params=['lock_backend_sqlite3_memory', 'lock_backend_sqlite3_filesystem'])
def lock_backend_sqlite3(request):
    # This fixtures will parameterize tests that use it with all database backends
    return request.getfixturevalue(request.param)


@pytest.fixture
def lock_manager_memory():
    return LocksManager.create('memory')


@pytest.fixture
def lock_manager_sqlite3():
    with tempfile.TemporaryDirectory() as tmpdirname:
        filename = os.path.join(tmpdirname, 'database.sqlite3')
        yield LocksManager.create('sqlite3', filename=filename)


@pytest.fixture(params=['lock_manager_memory', 'lock_manager_sqlite3'])
def lock_manager(request):
    # This fixtures will parameterize tests that use it with all database backends
    return request.getfixturevalue(request.param)
