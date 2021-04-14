import sqlite3
import time
from collections import namedtuple
from typing import Tuple, Iterator

from conan.cache.db.table import BaseDbTable
from conans.errors import ConanException
from conans.model.ref import PackageReference, ConanFileReference
from .references import ReferencesDbTable


class PackagesDbTable(BaseDbTable):
    table_name = 'conan_packages'
    columns_description = [('reference_pk', int),
                           ('package_id', str),
                           ('prev', str),
                           ('prev_order', int)]
    unique_together = ('reference_pk', 'package_id', 'prev')  # TODO: Add unittest
    references: ReferencesDbTable = None

    class DoesNotExist(ConanException):
        pass

    class MultipleObjectsReturned(ConanException):
        pass

    class AlreadyExist(ConanException):
        pass

    def create_table(self, conn: sqlite3.Cursor, references: ReferencesDbTable, if_not_exists: bool = True):
        super().create_table(conn, if_not_exists)
        self.references = references

    def _as_tuple(self, conn: sqlite3.Cursor, pref: PackageReference, prev_order: int):
        reference_pk = self.references.pk(conn, pref.ref)
        return self.row_type(reference_pk=reference_pk, package_id=pref.id, prev=pref.revision,
                             prev_order=prev_order)

    def _as_ref(self, conn: sqlite3.Cursor, row: namedtuple, ref: ConanFileReference = None):
        ref = ref or self.references.get(conn, row.reference_pk)
        return PackageReference.loads(f'{ref.full_str()}:{row.package_id}#{row.prev}',
                                      validate=False)

    def _where_clause(self, conn: sqlite3.Cursor, pref: PackageReference) -> Tuple[str, Tuple]:
        where = {
            self.columns.reference_pk: self.references.pk(conn, pref.ref),
            self.columns.package_id: pref.id,
            self.columns.prev: pref.revision
        }
        where_expr = ' AND '.join([f'{k} = ?' for k, v in where.items()])
        return where_expr, tuple(where.values())

    """
    Functions to manage the data in this table using Conan types
    """

    def save(self, conn: sqlite3.Cursor, pref: PackageReference):
        timestamp = int(time.time())
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        r = conn.execute(f'INSERT INTO {self.table_name} '
                         f'VALUES ({placeholders})', list(self._as_tuple(conn, pref, timestamp)))
        return r.lastrowid

    def update(self, conn: sqlite3.Cursor, pk: int, pref: PackageReference):
        """ Updates row 'pk' with values from 'pref' """
        timestamp = int(time.time())  # TODO: TBD: I will update the revision here too
        setters = ', '.join([f"{it} = ?" for it in self.columns])
        query = f"UPDATE {self.table_name} " \
                f"SET {setters} " \
                f"WHERE rowid = ?;"
        pref_as_tuple = list(self._as_tuple(conn, pref, timestamp))
        r = conn.execute(query, pref_as_tuple + [pk, ])
        return r.lastrowid

    def pk(self, conn: sqlite3.Cursor, pref: PackageReference) -> int:
        """ Returns the row matching the reference or fails """
        where_clause, where_values = self._where_clause(conn, pref)
        query = f'SELECT rowid FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query, where_values)
        row = r.fetchone()
        if not row:
            raise PackagesDbTable.DoesNotExist(f"No entry for package '{pref.full_str()}'")
        return row[0]

    def get(self, conn: sqlite3.Cursor, pk: int) -> PackageReference:
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE rowid = ?;'
        r = conn.execute(query, [pk, ])
        row = r.fetchone()
        return self._as_ref(conn, self.row_type(*row))

    def filter(self, conn: sqlite3.Cursor, ref: ConanFileReference,
               only_latest_prev: bool = False) -> Iterator[PackageReference]:
        """ Returns all the packages for a given reference """
        ref_pk = self.references.pk(conn, ref)
        if only_latest_prev:
            query = f'SELECT DISTINCT {self.columns.reference_pk}, {self.columns.package_id},' \
                    f'                {self.columns.prev}, MAX({self.columns.prev_order}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference_pk} = ? ' \
                    f'GROUP BY {self.columns.reference_pk}, {self.columns.package_id} ' \
                    f'ORDER BY MAX({self.columns.prev_order}) DESC'
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference_pk} = ?;'
        r = conn.execute(query, [ref_pk, ])
        for row in r.fetchall():
            yield self._as_ref(conn, self.row_type(*row), ref=ref)

    def search(self, conn: sqlite3.Cursor, ref: ConanFileReference, package_id: str,
               only_latest_prev: bool) -> Iterator[PackageReference]:
        ref_pk = self.references.pk(conn, ref)
        if only_latest_prev:
            query = f'SELECT DISTINCT {self.columns.reference_pk}, {self.columns.package_id},' \
                    f'                {self.columns.prev}, MAX({self.columns.prev_order}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference_pk} = ? AND {self.columns.package_id} = ?' \
                    f'GROUP BY {self.columns.reference_pk}, {self.columns.package_id} ' \
                    f'ORDER BY MAX({self.columns.prev_order}) DESC'
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference_pk} = ? AND {self.columns.package_id} = ?;'
        r = conn.execute(query, [ref_pk, package_id, ])
        for row in r.fetchall():
            yield self._as_ref(conn, self.row_type(*row), ref=ref)

    def latest_prev(self, conn: sqlite3.Cursor, pref: PackageReference) -> PackageReference:
        """ Returns the latest pref according to prev """
        ref_pk = self.references.pk(conn, pref.ref)
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE {self.columns.reference_pk} = ? AND {self.columns.package_id} = ? ' \
                f'ORDER BY {self.columns.prev} ' \
                f'LIMIT 1;'
        r = conn.execute(query, [ref_pk, pref.id, ])
        row = r.fetchone()
        return self._as_ref(conn, self.row_type(*row), pref.ref)
