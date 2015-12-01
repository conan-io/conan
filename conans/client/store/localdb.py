from conans.client.store.sqlite import SQLiteDB
from conans.errors import ConanException

USER_TABLE = "users"


class LocalDB(SQLiteDB):

    def __init__(self, dbfile):
        self.dbfile = dbfile
        super(LocalDB, self).__init__(dbfile)
        self.connect()
        self.init()

    def init(self):
        SQLiteDB.init(self)
        cursor = None
        try:
            cursor = self.connection.cursor()

            # To avoid multiple usernames in the login table, use always "login" as id
            cursor.execute("create table if not exists %s (id TEXT UNIQUE, "
                           "username TEXT UNIQUE, token TEXT)" % USER_TABLE)

        except Exception as e:
            message = "Could not initalize local cache"
            raise ConanException(message, e)
        finally:
            if cursor:
                cursor.close()

    def get_login(self):
        '''Returns login credentials.
        This method is also in charge of expiring them.
        '''
        try:
            statement = self.connection.cursor()
            statement.execute('select * from %s where id="login"' % USER_TABLE)
            rs = statement.fetchone()
            if not rs:
                return None, None
            name = rs[1]
            token = rs[2]
            return name, token
        except Exception:
            raise ConanException("Could read login\n Try removing '%s' file" % self.dbfile)

    def get_username(self):
        return self.get_login()[0]

    def set_login(self, login):
        """Login is a tuple of (login, token)"""
        try:
            statement = self.connection.cursor()
            statement.execute("INSERT OR REPLACE INTO %s (id, username, token) "
                              "VALUES (?, ?, ?)" % USER_TABLE,
                              ("login", login[0], login[1]))
            self.connection.commit()
        except Exception as e:
            raise ConanException("Could not store credentials", e)
