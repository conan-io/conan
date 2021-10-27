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

    def _set_clause(self, ref: ConanReference, path=None, timestamp=None, build_id=None):
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
            raise ConanReferenceDoesNotExistInDB(f"No entry for reference '{ref.full_reference}'")
        return self._as_dict(self.row_type(*row))

    def save(self, path, ref: ConanReference, timestamp):
        # we set the timestamp to 0 until they get a complete reference, here they
        # are saved with the temporary uuid one, we don't want to consider these
        # not yet built packages for search and so on
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        r = self._conn.execute(f'INSERT INTO {self.table_name} '
                               f'VALUES ({placeholders})',
                               [ref.reference, ref.rrev, path, timestamp])
        return r.lastrowid

    def update(self, old_ref: ConanReference, new_ref: ConanReference = None, new_path=None,
               new_timestamp=None):
        if not new_ref:
            new_ref = old_ref
        where_clause = self._where_clause(old_ref)
        set_clause = self._set_clause(new_ref, path=new_path, timestamp=new_timestamp)
        query = f"UPDATE {self.table_name} " \
                f"SET {set_clause} " \
                f"WHERE {where_clause};"
        try:
            r = self._conn.execute(query)
        except sqlite3.IntegrityError:
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{new_ref.full_reference}' already exists")
        return r.lastrowid

    def delete_by_path(self, path):
        query = f"DELETE FROM {self.table_name} " \
                f"WHERE path = ?;"
        r = self._conn.execute(query, (path,))
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
                    f'WHERE {self.columns.reference} = "{ref.reference}" ' \
                    f'{check_rrev} '
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference} = "{ref.reference}" ' \
                    f'{check_rrev} ' \
                    f'ORDER BY {self.columns.timestamp} DESC'
        print(query)
        r = self._conn.execute(query)
        for row in r.fetchall():
            yield self._as_dict(self.row_type(*row))
