import sqlite3

from conan.internal.cache.db.table import BaseDbTable
from conans.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class PackagesDBTable(BaseDbTable):
    table_name = 'packages'
    columns_description = [('reference', str),
                           ('rrev', str),
                           ('pkgid', str, True),
                           ('prev', str, True),
                           ('path', str, False, None, True),
                           ('timestamp', float),
                           ('build_id', str, True)]
    unique_together = ('reference', 'rrev', 'pkgid', 'prev')

    @staticmethod
    def _as_dict(row):
        ref = RecipeReference.loads(row.reference)
        ref.revision = row.rrev
        pref = PkgReference(ref, row.pkgid, row.prev, row.timestamp)
        return {
            "pref": pref,
            "build_id": row.build_id,
            "path": row.path,
        }

    def _where_clause(self, pref: PkgReference):
        where_dict = {
            self.columns.reference: str(pref.ref),
            self.columns.rrev: pref.ref.revision,
            self.columns.pkgid: pref.package_id,
            self.columns.prev: pref.revision,
        }
        where_expr = ' AND '.join(
            [f'{k}="{v}" ' if v is not None else f'{k} IS NULL' for k, v in where_dict.items()])
        return where_expr

    def _set_clause(self, pref: PkgReference, path=None, build_id=None):
        set_dict = {
            self.columns.reference: str(pref.ref),
            self.columns.rrev: pref.ref.revision,
            self.columns.pkgid: pref.package_id,
            self.columns.prev: pref.revision,
            self.columns.path: path,
            self.columns.timestamp: pref.timestamp,
            self.columns.build_id: build_id,
        }
        set_expr = ', '.join([f'{k} = "{v}"' for k, v in set_dict.items() if v is not None])
        return set_expr

    def get(self, pref: PkgReference):
        """ Returns the row matching the reference or fails """
        where_clause = self._where_clause(pref)
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = self._conn.execute(query)
        row = r.fetchone()
        if not row:
            raise ConanReferenceDoesNotExistInDB(f"No entry for package '{repr(pref)}'")
        return self._as_dict(self.row_type(*row))

    def create(self, path, pref: PkgReference, build_id):
        assert pref.revision
        assert pref.timestamp
        # we set the timestamp to 0 until they get a complete reference, here they
        # are saved with the temporary uuid one, we don't want to consider these
        # not yet built packages for search and so on
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        try:
            self._conn.execute(f'INSERT INTO {self.table_name} '
                               f'VALUES ({placeholders})',
                               [str(pref.ref), pref.ref.revision, pref.package_id, pref.revision,
                                path, pref.timestamp, build_id])
        except sqlite3.IntegrityError:
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{repr(pref)}' already exists")

    def update_timestamp(self, pref: PkgReference):
        assert pref.revision
        assert pref.timestamp
        where_clause = self._where_clause(pref)
        set_clause = self._set_clause(pref)
        query = f"UPDATE {self.table_name} " \
                f"SET {set_clause} " \
                f"WHERE {where_clause};"
        try:
            self._conn.execute(query)
        except sqlite3.IntegrityError:
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{repr(pref)}' already exists")

    def remove_recipe(self, ref: RecipeReference):
        # can't use the _where_clause, because that is an exact match on the package_id, etc
        query = f"DELETE FROM {self.table_name} " \
                f'WHERE {self.columns.reference} = "{str(ref)}" ' \
                f'AND {self.columns.rrev} = "{ref.revision}" '
        self._conn.execute(query)

    def remove(self, pref: PkgReference):
        where_clause = self._where_clause(pref)
        query = f"DELETE FROM {self.table_name} " \
                f"WHERE {where_clause};"
        self._conn.execute(query)

    def get_package_revisions_references(self, pref: PkgReference, only_latest_prev=False):
        assert pref.ref.revision, "To search package revisions you must provide a recipe revision."
        assert pref.package_id, "To search package revisions you must provide a package id."
        check_prev = f'AND {self.columns.prev} = "{pref.revision}" ' if pref.revision else ''
        if only_latest_prev:
            query = f'SELECT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.pkgid}, ' \
                    f'{self.columns.prev}, ' \
                    f'{self.columns.path}, ' \
                    f'MAX({self.columns.timestamp}), ' \
                    f'{self.columns.build_id} ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{pref.ref.revision}" ' \
                    f'AND {self.columns.reference} = "{str(pref.ref)}" ' \
                    f'AND {self.columns.pkgid} = "{pref.package_id}" ' \
                    f'{check_prev} ' \
                    f'AND {self.columns.prev} IS NOT NULL ' \
                    f'GROUP BY {self.columns.pkgid} '
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{pref.ref.revision}" ' \
                    f'AND {self.columns.reference} = "{str(pref.ref)}" ' \
                    f'AND {self.columns.pkgid} = "{pref.package_id}" ' \
                    f'{check_prev} ' \
                    f'AND {self.columns.prev} IS NOT NULL ' \
                    f'ORDER BY {self.columns.timestamp} DESC'
        r = self._conn.execute(query)
        for row in r.fetchall():
            yield self._as_dict(self.row_type(*row))

    def get_package_references(self, ref: RecipeReference, only_latest_prev=True):
        # Return the latest revisions
        assert ref.revision, "To search for package id's you must provide a recipe revision."
        # we select the latest prev for each package_id
        if only_latest_prev:
            query = f'SELECT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.pkgid}, ' \
                    f'{self.columns.prev}, ' \
                    f'{self.columns.path}, ' \
                    f'MAX({self.columns.timestamp}), ' \
                    f'{self.columns.build_id} ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{ref.revision}" ' \
                    f'AND {self.columns.reference} = "{str(ref)}" ' \
                    f'GROUP BY {self.columns.pkgid} '
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{ref.revision}" ' \
                    f'AND {self.columns.reference} = "{str(ref)}" ' \
                    f'AND {self.columns.prev} IS NOT NULL ' \
                    f'ORDER BY {self.columns.timestamp} DESC'
        r = self._conn.execute(query)
        for row in r.fetchall():
            yield self._as_dict(self.row_type(*row))
