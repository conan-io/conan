import sqlite3
import uuid
from contextlib import contextmanager

CONNECTION_TIMEOUT_SECONDS = 1  # Time a connection will wait when the database is locked


class Sqlite3MemoryMixin:
    timeout = CONNECTION_TIMEOUT_SECONDS  # FIXME: It doesn't work

    def __init__(self, unique_id: str = None):
        # Keep one connection open during all the application lifetime (that's why we need random id)
        self._unique_id = unique_id or str(uuid.uuid4())
        self._conn = sqlite3.connect(f'file:{self._unique_id}?mode=memory&cache=shared', uri=True)

    def __getstate__(self):
        raise Exception(
            'A memory Sqlite3 database is not pickable')  # TODO: Define if we want to share a memory database by running a 'multiprocessing' server (probably not)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(f'file:{self._unique_id}?mode=memory&cache=shared',
                               isolation_level=None, timeout=self.timeout, uri=True)
        try:
            conn.execute('begin EXCLUSIVE')
            yield conn.cursor()
            conn.execute("commit")
        except Exception as e:
            conn.execute("rollback")
            raise e
        finally:
            conn.close()


class Sqlite3FilesystemMixin:
    timeout = CONNECTION_TIMEOUT_SECONDS

    def __init__(self, filename: str):
        self._filename = filename

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self._filename, isolation_level=None, timeout=self.timeout)
        try:
            conn.execute('begin EXCLUSIVE')
            yield conn.cursor()
            conn.execute("commit")
        except Exception as e:
            conn.execute("rollback")
            raise e
        finally:
            conn.close()
