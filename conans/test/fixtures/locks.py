import os
import tempfile

import pytest

from conan.locks.backend_fasteners import LockBackendFasteners
from conan.locks.backend_sqlite3 import LockBackendSqlite3Memory, LockBackendSqlite3Filesystem
from conan.locks.locks_manager import LocksManager


@pytest.fixture
def lock_backend_sqlite3_memory():
    db = LockBackendSqlite3Memory()
    db.create_table()
    return db


@pytest.fixture
def lock_backend_sqlite3_filesystem():
    with tempfile.TemporaryDirectory() as tmpdirname:
        filename = os.path.join(tmpdirname, 'database.sqlite3')
        db = LockBackendSqlite3Filesystem(filename=filename)
        db.create_table()
        yield db


@pytest.fixture
def lock_backend_fasteners():
    with tempfile.TemporaryDirectory() as tmpdirname:
        backend = LockBackendFasteners(locks_directory=tmpdirname)
        yield backend


@pytest.fixture(params=['lock_backend_sqlite3_memory', 'lock_backend_sqlite3_filesystem',
                        'lock_backend_fasteners'])
def lock_backend(request):
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


@pytest.fixture
def lock_manager_fasteners():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield LocksManager.create('fasteners', locks_directory=tmpdirname)


@pytest.fixture(params=['lock_manager_memory', 'lock_manager_sqlite3', 'lock_manager_fasteners'])
def lock_manager(request):
    # This fixtures will parameterize tests that use it with all database backends
    return request.getfixturevalue(request.param)
