import os
import sqlite3
import threading
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from typing import Tuple, List

class BaseDbTable:
    table_name: str = None
    columns_description: List[Tuple[str, type]] = None
    row_type: namedtuple = None
    columns: namedtuple = None
    unique_together: tuple = None
    _thread_lock: threading.Lock = None
    _thread_lock_storage = defaultdict(threading.Lock)
    _process_lock = None
    _process_lock_storage = {}

    def __init__(self, filename):
        self.filename = filename
        column_names: List[str] = [it[0] for it in self.columns_description]
        self.row_type = namedtuple('_', column_names)
        self.columns = self.row_type(*column_names)
        # Thread-level lock for single-process safety
        self._thread_lock = self._thread_lock_storage[self.filename]
        # Inter-process lock for multi-process safety
        if self.filename not in self._process_lock_storage:
            from conan.internal.cache.concurrency_lock import ConcurrencyLock
            db_dir = os.path.dirname(self.filename) or os.getcwd()
            self._process_lock_storage[self.filename] = ConcurrencyLock(db_dir)
        self._process_lock = self._process_lock_storage[self.filename]

    @contextmanager
    def db_connection(self, use_inter_process_lock=False):
        """Get a DB connection with optional inter-process locking.

        Args:
            use_inter_process_lock: If True, acquire inter-process lock before connecting.
                Only needed for operations that must be atomic across processes (e.g., table creation).
                Regular queries don't need this - SQLite WAL mode handles concurrency.
        """
        if use_inter_process_lock:
            # Use inter-process lock for operations that must be atomic across processes
            db_name = os.path.basename(self.filename)
            lock_ctx = self._process_lock.lock(f"db_init_{db_name}")
        else:
            # For normal queries, just use thread lock - SQLite WAL mode handles inter-process concurrency
            from contextlib import nullcontext
            lock_ctx = nullcontext()

        with lock_ctx:
            # Also acquire thread lock for thread safety within this process
            self._thread_lock.acquire()
            try:
                # isolation_level=None, puts it in regular SQLITE autocommit mode, every
                # connection.execute() will autocommit
                connection = sqlite3.connect(self.filename, isolation_level=None)
                try:
                    # Enable WAL mode for better concurrency (multiple readers, non-blocking writes)
                    # WAL mode persists in the database file, so this is mostly a no-op after first run
                    connection.execute("PRAGMA journal_mode=WAL")
                    # Set busy timeout to handle high-concurrency scenarios
                    # When many processes access the DB simultaneously (e.g., in CI with parallel tests),
                    # this prevents immediate "database is locked" failures
                    connection.execute("PRAGMA busy_timeout=60000")
                    yield connection
                finally:
                    connection.close()
            finally:
                self._thread_lock.release()

    def create_table(self):
        """Create table with inter-process locking to prevent concurrent creation races."""
        def field(name, typename, nullable=False, unique=False):
            field_str = name
            if typename is str:
                field_str += ' text'
            elif typename is int:
                field_str += ' integer'
            else:
                assert typename is float, f"sqlite3 type not mapped for type '{typename}'"
                field_str += ' real'

            if not nullable:
                field_str += ' NOT NULL'

            if unique:
                field_str += ' UNIQUE'

            return field_str

        fields = ', '.join([field(*it) for it in self.columns_description])
        guard = 'IF NOT EXISTS'
        table_checks = f", UNIQUE({', '.join(self.unique_together)})" if self.unique_together else ''
        # Use inter-process lock for table creation to prevent race conditions
        with self.db_connection(use_inter_process_lock=True) as conn:
            conn.execute(f"CREATE TABLE {guard} {self.table_name} ({fields} {table_checks});")
