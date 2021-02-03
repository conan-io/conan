import os
import sqlite3

from conan.locks.backend import LockBackend


class LockBackendSqlite3(LockBackend):
    # Sqlite3 backend to store locks. It will store the PID of every writer or reader before
    # the can proceed to the resource (exclusive writer strategy).

    LockId = int
    _table_name = 'conan_locks'
    _column_resource = 'resource'
    _column_pid = 'pid'
    _column_writer = 'writer'

    def __init__(self, filename: str):
        # We won't run out of file descriptors, so implementation here is up to the threading
        # model decided for Conan
        self._conn = sqlite3.connect(filename)

    def create_table(self, if_not_exists: bool = True):
        guard = 'IF NOT EXISTS' if if_not_exists else ''
        query = f"""
        CREATE TABLE {guard} {self._table_name} (
            {self._column_resource} text NOT NULL,
            {self._column_pid} integer NOT NULL,
            {self._column_writer} BOOLEAN NOT NULL CHECK ({self._column_writer} IN (0,1))
        );
        """
        with self._conn:
            self._conn.execute(query)

    def try_acquire(self, resource: str, blocking: bool) -> LockId:
        # Returns a backend-id
        with self._conn:
            # Check if any is using the resource
            result = self._conn.execute(f'SELECT {self._column_pid}, {self._column_writer} '
                                        f'FROM {self._table_name} '
                                        f'WHERE {self._column_resource} = "{resource}";')
            if blocking and result.fetchone():
                raise Exception(f"Resource '{resource}' is already blocked")

            # Check if a writer (exclusive) is blocking
            blocked = any([it[1] for it in result.fetchall()])
            if blocked:
                raise Exception(f"Resource '{resource}' is blocked by a writer")

            # Add me as a reader, one more reader
            blocking_value = 1 if blocking else 0
            result = self._conn.execute(f'INSERT INTO {self._table_name} '
                                        f'VALUES ("{resource}", {os.getpid()}, {blocking_value})')
            return result.lastrowid

    def release(self, backend_id: LockId):
        with self._conn:
            self._conn.execute(f'DELETE FROM {self._table_name} WHERE rowid={backend_id}')
