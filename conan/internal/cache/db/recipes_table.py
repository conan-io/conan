import sqlite3

from conan.internal.cache.db.table import BaseDbTable
from conans.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB
from conans.model.recipe_ref import RecipeReference


class RecipesDBTable(BaseDbTable):
    table_name = 'recipes'
    columns_description = [('reference', str),
                           ('rrev', str),
                           ('path', str, False, None, True),
                           ('timestamp', float)]
    unique_together = ('reference', 'rrev')

    @staticmethod
    def _as_dict(row):
        ref = RecipeReference.loads(row.reference)
        ref.revision = row.rrev
        ref.timestamp = row.timestamp
        return {
            "ref": ref,
            "path": row.path,
        }

    def _where_clause(self, ref):
        assert isinstance(ref, RecipeReference)
        where_dict = {
            self.columns.reference: str(ref),
            self.columns.rrev: ref.revision,
        }
        where_expr = ' AND '.join(
            [f'{k}="{v}" ' if v is not None else f'{k} IS NULL' for k, v in where_dict.items()])
        return where_expr

    def _set_clause(self, ref: RecipeReference, path=None):
        set_dict = {
            self.columns.reference: str(ref),
            self.columns.rrev: ref.revision,
            self.columns.path: path,
            self.columns.timestamp: ref.timestamp,
        }
        set_expr = ', '.join([f'{k} = "{v}"' for k, v in set_dict.items() if v is not None])
        return set_expr

    def get(self, ref: RecipeReference):
        """ Returns the row matching the reference or fails """
        where_clause = self._where_clause(ref)
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = self._conn.execute(query)
        row = r.fetchone()
        if not row:
            raise ConanReferenceDoesNotExistInDB(f"No entry for recipe '{repr(ref)}'")
        return self._as_dict(self.row_type(*row))

    def create(self, path, ref: RecipeReference):
        assert ref is not None
        assert ref.revision is not None
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        try:
            self._conn.execute(f'INSERT INTO {self.table_name} '
                               f'VALUES ({placeholders})',
                               [str(ref), ref.revision, path, ref.timestamp])
        except sqlite3.IntegrityError as e:
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{repr(ref)}' already exists")

    def update_timestamp(self, ref: RecipeReference):
        assert ref.revision is not None
        assert ref.timestamp is not None
        where_clause = self._where_clause(ref)
        query = f"UPDATE {self.table_name} " \
                f'SET {self.columns.timestamp} = "{ref.timestamp}" ' \
                f"WHERE {where_clause};"
        self._conn.execute(query)

    def remove(self, ref: RecipeReference):
        where_clause = self._where_clause(ref)
        query = f"DELETE FROM {self.table_name} " \
                f"WHERE {where_clause};"
        self._conn.execute(query)

    # returns all different conan references (name/version@user/channel)
    def all_references(self):
        query = f'SELECT DISTINCT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.path} ,' \
                    f'{self.columns.timestamp} ' \
                    f'FROM {self.table_name} ' \
                    f'ORDER BY {self.columns.timestamp} DESC'
        r = self._conn.execute(query)
        result = [self._as_dict(self.row_type(*row)) for row in r.fetchall()]
        return result

    def get_recipe_revisions_references(self, ref: RecipeReference, only_latest_rrev=False):
        # FIXME: This is very fragile, we should disambiguate the function and check that revision
        #        is always None if we want to check the revisions. Do another function to get the
        #        time or check existence if needed
        check_rrev = f'AND {self.columns.rrev} = "{ref.revision}" ' if ref.revision else ''
        if only_latest_rrev:
            query = f'SELECT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.path}, ' \
                    f'MAX({self.columns.timestamp}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference}="{str(ref)}" ' \
                    f'{check_rrev} '\
                    f'GROUP BY {self.columns.reference} '  # OTHERWISE IT FAILS THE MAX()
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference} = "{str(ref)}" ' \
                    f'{check_rrev} ' \
                    f'ORDER BY {self.columns.timestamp} DESC'

        r = self._conn.execute(query)
        return [self._as_dict(self.row_type(*row)) for row in r.fetchall()]
