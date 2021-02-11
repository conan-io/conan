import sqlite3
import uuid
from contextlib import contextmanager


class Sqlite3MemoryMixin:
    def __init__(self, unique_id: str = None):
        # Keep one connection open during all the application lifetime (that's why we need random id)
        self._unique_id = unique_id or str(uuid.uuid4())
        self._conn = sqlite3.connect(f'file:{self._unique_id}?mode=memory&cache=shared', uri=True)

    def __getstate__(self):
        raise Exception(
            'A memory Sqlite3 database is not pickable')  # TODO: Define if we want to share a memory database by running a 'multiprocessing' server (probably not)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(f'file:{self._unique_id}?mode=memory&cache=shared', uri=True)
        try:
            yield conn.cursor()
        finally:
            conn.commit()
            conn.close()


class Sqlite3FilesystemMixin:
    def __init__(self, filename: str):
        self._filename = filename

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self._filename)
        try:
            yield conn.cursor()
        finally:
            conn.commit()
            conn.close()
