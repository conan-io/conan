import os
import sqlite3
from sqlite3 import OperationalError

from conans.errors import ConanException
from contextlib import contextmanager

REMOTES_USER_TABLE = "users_remotes"


class LocalDB(object):

    def __init__(self, dbfile):
        self.dbfile = dbfile

    @staticmethod
    def create(dbfile, clean=False):
        # Create the database file if it doesn't exist
        if not os.path.exists(dbfile):
            par = os.path.dirname(dbfile)
            if not os.path.exists(par):
                os.makedirs(par)
            db = open(dbfile, 'w+')
            db.close()

        connection = sqlite3.connect(dbfile, detect_types=sqlite3.PARSE_DECLTYPES)

        try:
            cursor = connection.cursor()
            if clean:
                cursor.execute("drop table if exists %s" % REMOTES_USER_TABLE)
                try:
                    # https://github.com/ghaering/pysqlite/issues/109
                    connection.isolation_level = None
                    cursor.execute('VACUUM')  # Make sure the DB is cleaned, drop doesn't do that
                except OperationalError:
                    pass

            cursor.execute("create table if not exists %s "
                           "(remote_url TEXT UNIQUE, user TEXT, token TEXT)" % REMOTES_USER_TABLE)
        except Exception as e:
            message = "Could not initialize local sqlite database"
            raise ConanException(message, e)
        finally:
            connection.close()

        return LocalDB(dbfile)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.dbfile, detect_types=sqlite3.PARSE_DECLTYPES)
        connection.text_factory = str
        try:
            yield connection
        finally:
            connection.close()

    def get_login(self, remote_url):
        """ Returns login credentials. This method is also in charge of expiring them. """
        with self._connect() as connection:
            try:
                statement = connection.cursor()
                statement.execute('select user, token from %s where remote_url="%s"'
                                  % (REMOTES_USER_TABLE, remote_url))
                rs = statement.fetchone()
                if not rs:
                    return None, None
                name = rs[0]
                token = rs[1]
                return name, token
            except Exception:
                raise ConanException("Couldn't read login\n Try removing '%s' file" % self.dbfile)

    def get_username(self, remote_url):
        return self.get_login(remote_url)[0]

    def set_login(self, login, remote_url):
        """ Login is a tuple of (user, token) """
        with self._connect() as connection:
            try:
                statement = connection.cursor()
                statement.execute("INSERT OR REPLACE INTO %s (remote_url, user, token) "
                                  "VALUES (?, ?, ?)" % REMOTES_USER_TABLE,
                                  (remote_url, login[0], login[1]))
                connection.commit()
            except Exception as e:
                raise ConanException("Could not store credentials %s" % str(e))
