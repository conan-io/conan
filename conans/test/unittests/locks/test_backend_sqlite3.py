import pytest


class TestLockBackendSqlite3Memory:

    def test_two_writers(self, lock_backend_sqlite3):
        db = lock_backend_sqlite3
        db.create_table()

        db.try_acquire('resid', blocking=True)
        with pytest.raises(Exception) as excinfo:
            db.try_acquire('resid', blocking=True)
        assert "Resource 'resid' is already blocked" == str(excinfo.value)

    def test_reader_after_writer(self, lock_backend_sqlite3):
        db = lock_backend_sqlite3
        db.create_table()

        db.try_acquire('resid', blocking=True)
        with pytest.raises(Exception) as excinfo:
            db.try_acquire('resid', blocking=False)
        assert "Resource 'resid' is already blocked by a writer" == str(excinfo.value)

    def test_writer_after_reader(self, lock_backend_sqlite3):
        db = lock_backend_sqlite3
        db.create_table()

        db.try_acquire('resid', blocking=False)
        with pytest.raises(Exception) as excinfo:
            db.try_acquire('resid', blocking=True)
        assert "Resource 'resid' is already blocked" == str(excinfo.value)

    def test_reader_after_reader(self, lock_backend_sqlite3):
        db = lock_backend_sqlite3
        db.create_table()

        db.try_acquire('resid', blocking=False)
        db.try_acquire('resid', blocking=False)

    def test_remove_lock(self, lock_backend_sqlite3):
        db = lock_backend_sqlite3
        db.create_table()

        # Writer after reader
        reader_id = db.try_acquire('resid', blocking=False)
        with pytest.raises(Exception) as excinfo:
            db.try_acquire('resid', blocking=True)
        assert "Resource 'resid' is already blocked" == str(excinfo.value)

        # Remove the reader
        db.release(reader_id)
        db.try_acquire('resid', blocking=True)
