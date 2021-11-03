import sqlite3

from conan.cache.conan_reference import ConanReference
from conan.cache.db.table import BaseDbTable
from conans.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB


class RecipesDBTable(BaseDbTable):
    table_name = 'recipes'
    columns_description = [('reference', str),
                           ('rrev', str),
                           ('path', str, False, None, True),
                           ('timestamp', float)]

    unique_together = ('reference', 'rrev')

    @staticmethod
    def _as_dict(row):
        return {
            "reference": row.reference,
            "rrev": row.rrev,
            "path": row.path,
            "timestamp": row.timestamp
        }

    def _where_clause(self, ref: ConanReference):
        where_dict = {
            self.columns.reference: ref.reference,
            self.columns.rrev: ref.rrev,
        }
        where_expr = ' AND '.join(
            [f'{k}="{v}" ' if v is not None else f'{k} IS NULL' for k, v in where_dict.items()])
        return where_expr

    def _set_clause(self, ref: ConanReference, path=None, timestamp=None):
        set_dict = {
            self.columns.reference: ref.reference,
            self.columns.rrev: ref.rrev,
            self.columns.path: path,
            self.columns.timestamp: timestamp,
        }
        set_expr = ', '.join([f'{k} = "{v}"' for k, v in set_dict.items() if v is not None])
        return set_expr

    def get(self, ref: ConanReference):
        """ Returns the row matching the reference or fails """
        where_clause = self._where_clause(ref)
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = self._conn.execute(query)
        row = r.fetchone()
        if not row:
            raise ConanReferenceDoesNotExistInDB(f"No entry for recipe '{ref.full_reference}'")
        return self._as_dict(self.row_type(*row))

    def create(self, path, ref: ConanReference, timestamp):
        assert ref.reference is not None
        assert ref.rrev is not None
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        try:
            r = self._conn.execute(f'INSERT INTO {self.table_name} '
                                   f'VALUES ({placeholders})',
                                   [ref.reference, ref.rrev, path, timestamp])
        except sqlite3.IntegrityError:
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{ref.full_reference}' already exists")
        return r.lastrowid

    def update_timestamp(self, ref: ConanReference, new_timestamp=None):
        assert ref is not None
        assert ref.reference is not None
        assert ref.rrev is not None
        where_clause = self._where_clause(ref)
        query = f"UPDATE {self.table_name} " \
                f'SET {self.columns.timestamp} = "{new_timestamp}" ' \
                f"WHERE {where_clause};"
        r = self._conn.execute(query)
        return r.lastrowid

    def remove(self, ref: ConanReference):
        where_clause = self._where_clause(ref)
        query = f"DELETE FROM {self.table_name} " \
                f"WHERE {where_clause};"
        r = self._conn.execute(query)
        return r.lastrowid

    # returns all different conan references (name/version@user/channel)
    def all_references(self, only_latest_rrev=False):
        if only_latest_rrev:
            query = f'SELECT DISTINCT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.path}, ' \
                    f'FROM {self.table_name} ' \
                    f'ORDER BY {self.columns.timestamp} DESC'
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'ORDER BY {self.columns.timestamp} DESC;'
        r = self._conn.execute(query)
        for row in r.fetchall():
            yield self._as_dict(self.row_type(*row))

    def get_recipe_revisions(self, ref: ConanReference, only_latest_rrev=False):
        check_rrev = f'AND {self.columns.rrev} = "{ref.rrev}" ' if ref.rrev else ''
        if only_latest_rrev:
            query = f'SELECT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.path}, ' \
                    f'MAX({self.columns.timestamp}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference}="{ref.reference}" ' \
                    f'{check_rrev} '\
                    f'GROUP BY {self.columns.reference} '  # OTHERWISE IT FAILS THE MAX()
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference} = "{ref.reference}" ' \
                    f'{check_rrev} ' \
                    f'ORDER BY {self.columns.timestamp} DESC'

        r = self._conn.execute(query)
        for row in r.fetchall():
            yield self._as_dict(self.row_type(*row))
