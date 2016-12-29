import sqlite3
import os
from conans.errors import ConanException


class SQLiteDB(object):
    def __init__(self, dbfile_path):
        if not os.path.exists(dbfile_path):
            par = os.path.dirname(dbfile_path)
            if not os.path.exists(par):
                os.makedirs(par)
            dbfile = open(dbfile_path, 'w+')
            dbfile.close()
        self.dbfile = dbfile_path

    def connect(self):
        try:
            self.connection = sqlite3.connect(self.dbfile,
                                              detect_types=sqlite3.PARSE_DECLTYPES)
            self.connection.text_factory = str
            statement = None
            try:
                statement = self.connection.cursor()
            except Exception as e:
                raise ConanException(e)
            finally:
                if statement:
                    statement.close()
        except Exception as e:
            raise ConanException('Could not connect to local cache', e)

    def disconnect(self):
        self.connection.close()
