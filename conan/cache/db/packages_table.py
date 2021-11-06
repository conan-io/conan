import sqlite3

from conan.cache.conan_reference import ConanReference
from conan.cache.db.table import BaseDbTable
from conans.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB


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
        return {
            "reference": row.reference,
            "rrev": row.rrev,
            "pkgid": row.pkgid,
            "build_id": row.build_id,
            "prev": row.prev,
            "path": row.path,
            "timestamp": row.timestamp
        }

    def _where_clause(self, ref: ConanReference):
        where_dict = {
            self.columns.reference: ref.reference,
            self.columns.rrev: ref.rrev,
            self.columns.pkgid: ref.pkgid,
            self.columns.prev: ref.prev,
        }
        where_expr = ' AND '.join(
            [f'{k}="{v}" ' if v is not None else f'{k} IS NULL' for k, v in where_dict.items()])
        return where_expr

    def _set_clause(self, ref: ConanReference, path=None, timestamp=None, build_id=None):
        set_dict = {
            self.columns.reference: ref.reference,
            self.columns.rrev: ref.rrev,
            self.columns.pkgid: ref.pkgid,
            self.columns.prev: ref.prev,
            self.columns.path: path,
            self.columns.timestamp: timestamp,
            self.columns.build_id: build_id,
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
            raise ConanReferenceDoesNotExistInDB(f"No entry for package '{ref.full_reference}'")
        return self._as_dict(self.row_type(*row))

    def create(self, path, ref: ConanReference, timestamp, build_id):
        assert ref.prev
        # we set the timestamp to 0 until they get a complete reference, here they
        # are saved with the temporary uuid one, we don't want to consider these
        # not yet built packages for search and so on
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        try:
            r = self._conn.execute(f'INSERT INTO {self.table_name} '
                                   f'VALUES ({placeholders})',
                                   [ref.reference, ref.rrev, ref.pkgid, ref.prev, path, timestamp,
                                    build_id])
        except sqlite3.IntegrityError:
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{ref.full_reference}' already exists")

        return r.lastrowid

    def update_timestamp(self, ref: ConanReference, new_timestamp=None):
        assert ref.prev
        where_clause = self._where_clause(ref)
        set_clause = self._set_clause(ref, timestamp=new_timestamp)
        query = f"UPDATE {self.table_name} " \
                f"SET {set_clause} " \
                f"WHERE {where_clause};"
        try:
            r = self._conn.execute(query)
        except sqlite3.IntegrityError:
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{ref.full_reference}' already exists")
        return r.lastrowid

    def remove(self, ref: ConanReference):
        where_clause = self._where_clause(ref)
        query = f"DELETE FROM {self.table_name} " \
                f"WHERE {where_clause};"
        r = self._conn.execute(query)
        return r.lastrowid

    def get_package_revisions(self, ref: ConanReference, only_latest_prev=False):
        assert ref.rrev, "To search for package revisions you must provide a recipe revision."
        assert ref.pkgid, "To search for package revisions you must provide a package id."
        check_prev = f'AND {self.columns.prev} = "{ref.prev}" ' if ref.prev else ''
        if only_latest_prev:
            query = f'SELECT {self.columns.reference}, ' \
                    f'{self.columns.rrev}, ' \
                    f'{self.columns.pkgid}, ' \
                    f'{self.columns.prev}, ' \
                    f'{self.columns.path}, ' \
                    f'MAX({self.columns.timestamp}), ' \
                    f'{self.columns.build_id} ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{ref.rrev}" ' \
                    f'AND {self.columns.reference} = "{ref.reference}" ' \
                    f'AND {self.columns.pkgid} = "{ref.pkgid}" ' \
                    f'{check_prev} ' \
                    f'AND {self.columns.prev} IS NOT NULL ' \
                    f'GROUP BY {self.columns.pkgid} '
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.rrev} = "{ref.rrev}" ' \
                    f'AND {self.columns.reference} = "{ref.reference}" ' \
                    f'AND {self.columns.pkgid} = "{ref.pkgid}" ' \
                    f'{check_prev} ' \
                    f'AND {self.columns.prev} IS NOT NULL ' \
                    f'ORDER BY {self.columns.timestamp} DESC'
        r = self._conn.execute(query)
        for row in r.fetchall():
            yield self._as_dict(self.row_type(*row))

    def get_package_references(self, ref: ConanReference):
        assert ref.rrev, "To search for package id's you must provide a recipe revision."
        # we select the latest prev for each package_id
        query = f'SELECT {self.columns.reference}, ' \
                f'{self.columns.rrev}, ' \
                f'{self.columns.pkgid}, ' \
                f'{self.columns.prev}, ' \
                f'{self.columns.path}, ' \
                f'{self.columns.timestamp}, ' \
                f'{self.columns.build_id} ' \
                f'FROM {self.table_name} ' \
                f'WHERE {self.columns.rrev} = "{ref.rrev}" ' \
                f'AND {self.columns.reference} = "{ref.reference}" ' \
                f'AND {self.columns.pkgid} IS NOT NULL ' \
                f'GROUP BY {self.columns.pkgid} ' \
                f'ORDER BY {self.columns.timestamp} DESC'
        r = self._conn.execute(query)
        for row in r.fetchall():
            yield self._as_dict(self.row_type(*row))
