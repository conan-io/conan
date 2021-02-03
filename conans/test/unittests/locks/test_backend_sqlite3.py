import pytest

from conan.locks.backend_sqlite3 import LockBackendSqlite3


class TestBackendSqlite3:

    def test_two_writers(self):
        db = LockBackendSqlite3(':memory:')
        db.create_table()

        db.try_acquire('resid', blocking=True)
        with pytest.raises(Exception) as excinfo:
            db.try_acquire('resid', blocking=True)
        assert "Resource 'resid' is already blocked" == str(excinfo.value)

    def test_reader_after_writer(self):
        db = LockBackendSqlite3(':memory:')
        db.create_table()

        db.try_acquire('resid', blocking=True)
        with pytest.raises(Exception) as excinfo:
            db.try_acquire('resid', blocking=False)
        assert "Resource 'resid' is blocked by a writer" == str(excinfo.value)

    def test_writer_after_reader(self):
        db = LockBackendSqlite3(':memory:')
        db.create_table()

        db.try_acquire('resid', blocking=False)
        with pytest.raises(Exception) as excinfo:
            db.try_acquire('resid', blocking=True)
        assert "Resource 'resid' is already blocked" == str(excinfo.value)

    def test_reader_after_reader(self):
        db = LockBackendSqlite3(':memory:')
        db.create_table()

        db.try_acquire('resid', blocking=False)
        db.try_acquire('resid', blocking=False)

    def test_remove_lock(self):
        db = LockBackendSqlite3(':memory:')
        db.create_table()

        # Writer after reader
        reader_id = db.try_acquire('resid', blocking=False)
        with pytest.raises(Exception) as excinfo:
            db.try_acquire('resid', blocking=True)
        assert "Resource 'resid' is already blocked" == str(excinfo.value)

        # Remove the reader
        db.release(reader_id)
        db.try_acquire('resid', blocking=True)
