import pytest

from conan.locks.backend_sqlite3 import LockBackendSqlite3
from conan.locks.backend import LockBackend
from locks.backend_fasteners import LockBackendFasteners


class TestLockBackendSqlite3Memory:

    def test_two_writers(self, lock_backend: LockBackend):
        db = lock_backend

        with db.lock('resid', blocking=True):
            with pytest.raises(Exception) as excinfo:
                with db.lock('resid', blocking=True):
                    pass
            assert "Resource 'resid' is already blocked" == str(excinfo.value)

    def test_reader_after_writer(self, lock_backend: LockBackend):
        db = lock_backend

        with db.lock('resid', blocking=True):
            with pytest.raises(Exception) as excinfo:
                with db.lock('resid', blocking=False):
                    pass
            assert "Resource 'resid' is already blocked by a writer" == str(excinfo.value)

    def test_writer_after_reader(self, lock_backend: LockBackend):
        db = lock_backend

        with db.lock('resid', blocking=False):
            with pytest.raises(Exception) as excinfo:
                with db.lock('resid', blocking=True):
                    pass
            assert "Resource 'resid' is already blocked" == str(excinfo.value)

    def test_reader_after_reader(self, lock_backend: LockBackend):
        db = lock_backend

        with db.lock('resid', blocking=False):
            with db.lock('resid', blocking=False):
                pass

    def test_remove_lock(self, lock_backend: LockBackend):
        db = lock_backend

        # Writer after reader
        with db.lock('resid', blocking=False):
            with pytest.raises(Exception) as excinfo:
                with db.lock('resid', blocking=True):
                    pass
            assert "Resource 'resid' is already blocked" == str(excinfo.value)

        # Now I can the writer
        with db.lock('resid', blocking=True):
            pass
