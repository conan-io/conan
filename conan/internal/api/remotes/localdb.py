import os
import sqlite3
from contextlib import contextmanager
from sqlite3 import OperationalError

from conan.errors import ConanException
from conan.internal.api.remotes import encrypt

REMOTES_USER_TABLE = "users_remotes"
LOCALDB = ".conan.db"

_localdb_encryption_key = os.environ.pop('CONAN_LOGIN_ENCRYPTION_KEY', None)


class LocalDB:
    """
    Local SQLite database for storing user credentials.

    The database is initialized atomically - SQLite handles file creation
    and CREATE TABLE IF NOT EXISTS is idempotent, making this safe for
    concurrent access from multiple processes.
    """

    def __init__(self, dbfolder):
        self.dbfile = os.path.join(dbfolder, LOCALDB)
        self.encryption_key = _localdb_encryption_key

        # Ensure parent directory exists
        par = os.path.dirname(self.dbfile)
        os.makedirs(par, exist_ok=True)

        # Use a file lock to serialize database initialization across processes
        # This prevents lock contention when many processes initialize simultaneously
        # (e.g., during parallel test runs with 48+ cores)
        import fcntl
        lock_path = self.dbfile + ".init.lock"

        # Retry loop to handle TOCTOU race: directory deleted after makedirs but before open
        max_retries = 3
        for attempt in range(max_retries):
            try:
                os.makedirs(par, exist_ok=True)
                lock_file = open(lock_path, 'w')
                break
            except FileNotFoundError:
                if attempt == max_retries - 1:
                    raise
                continue

        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

            # SQLite's connect() atomically creates the file if it doesn't exist.
            # CREATE TABLE IF NOT EXISTS is idempotent and safe for concurrent execution.
            # This avoids the race condition of check-then-create patterns.
            with self._connect() as connection:
                try:
                    cursor = connection.cursor()
                    cursor.execute("create table if not exists %s "
                                   "(remote_url TEXT UNIQUE, user TEXT, "
                                   "token TEXT, refresh_token TEXT)" % REMOTES_USER_TABLE)
                except Exception as e:
                    message = f"Could not initialize local sqlite database {self.dbfile}"
                    raise ConanException(message, e)

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
        finally:
            try:
                os.remove(lock_path)
            except (OSError, FileNotFoundError):
                pass

    def _encode(self, value):
        if value and self.encryption_key:
            return encrypt.encode(value, self.encryption_key)
        return value

    def _decode(self, value):
        if value and self.encryption_key:
            return encrypt.decode(value, self.encryption_key)
        return value

    def clean(self, remote_url=None):
        with self._connect() as connection:
            try:
                cursor = connection.cursor()
                query = "DELETE FROM %s" % REMOTES_USER_TABLE
                if remote_url:
                    query += " WHERE remote_url='{}'".format(remote_url)
                cursor.execute(query)
                try:
                    # https://github.com/ghaering/pysqlite/issues/109
                    connection.isolation_level = None
                    cursor.execute('VACUUM')  # Make sure the DB is cleaned, drop doesn't do that
                except OperationalError:
                    pass
            except Exception as e:
                raise ConanException("Could not initialize local sqlite database", e)

    @contextmanager
    def _connect(self):
        # isolation_level=None enables autocommit mode for immediate visibility
        connection = sqlite3.connect(self.dbfile, detect_types=sqlite3.PARSE_DECLTYPES,
                                    isolation_level=None)
        connection.text_factory = str
        try:
            # Enable WAL mode for better concurrency (multiple readers, non-blocking writes)
            # This is especially important when multiple threads/processes authenticate simultaneously
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
        finally:
            connection.close()

    def get_login(self, remote_url):
        """ Returns login credentials. This method is also in charge of expiring them. """
        with self._connect() as connection:
            try:
                statement = connection.cursor()
                statement.execute("select user, token, refresh_token from %s where remote_url='%s'"
                                  % (REMOTES_USER_TABLE, remote_url))
                rs = statement.fetchone()
                if not rs:
                    return None, None, None
                name = rs[0]
                token = self._decode(rs[1])
                refresh_token = self._decode(rs[2])
                return name, token, refresh_token
            except Exception:
                raise ConanException("Couldn't read login\n Try removing '%s' file" % self.dbfile)

    def get_username(self, remote_url):
        return self.get_login(remote_url)[0]

    def store(self, user, token, refresh_token, remote_url):
        """ Login is a tuple of (user, token) """
        with self._connect() as connection:
            try:
                token = self._encode(token)
                refresh_token = self._encode(refresh_token)
                statement = connection.cursor()
                statement.execute("INSERT OR REPLACE INTO %s (remote_url, user, token, "
                                  "refresh_token) "
                                  "VALUES (?, ?, ?, ?)" % REMOTES_USER_TABLE,
                                  (remote_url, user, token, refresh_token))
                # No need to commit explicitly in autocommit mode (isolation_level=None)
                # The execute() above already committed the transaction
                # Force WAL checkpoint to ensure token updates are immediately visible to other processes
                # Critical for parallel downloads where worker processes need to see re-authenticated tokens
                connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception as e:
                raise ConanException("Could not store credentials %s" % str(e))
