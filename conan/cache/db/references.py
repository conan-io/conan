import sqlite3
import time
from collections import namedtuple
from typing import List, Iterator

from conan.cache.db.table import BaseDbTable
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference


class ReferencesDbTable(BaseDbTable):
    table_name = 'conan_references'
    columns_description = [('reference', str),
                           ('rrev', str),
                           ('pkgid', str, True),
                           ('prev', str, True),
                           ('path', str, False, None, True),
                           ('timestamp', int)]

    class DoesNotExist(ConanException):
        pass

    class MultipleObjectsReturned(ConanException):
        pass

    class AlreadyExist(ConanException):
        pass

    def _as_ref(self, row: namedtuple):
        if row.prev:
            return PackageReference.loads(f'{row.reference}#{row.rrev}:{row.pkgid}#{row.prev}',
                                          validate=False)
        else:
            return ConanFileReference.loads(f'{row.reference}#{row.rrev}', validate=False)

    def _where_clause(self, reference, rrev, pkgid, prev):
        where_dict = {
            self.columns.reference: reference,
            self.columns.rrev: rrev,
            self.columns.pkgid: pkgid,
            self.columns.prev: prev,
        }
        where_expr = ' AND '.join(
            [f'{k}="{v}" ' if v is not None else f'{k} IS NULL' for k, v in where_dict.items()])
        return where_expr

    def _set_clause(self, path=None, reference=None, rrev=None, pkgid=None, prev=None,
                    timestamp=None):
        set_dict = {
            self.columns.reference: reference,
            self.columns.rrev: rrev,
            self.columns.pkgid: pkgid,
            self.columns.prev: prev,
            self.columns.path: path,
            self.columns.timestamp: timestamp,
        }
        set_expr = ', '.join([f"{k} = ?" for k, v in set_dict.items() if v is not None])
        return set_expr, tuple([v for v in set_dict.values() if v is not None])

    def get_path_ref(self, conn: sqlite3.Cursor, ref) -> str:
        """ Returns the row matching the reference or fails """
        where_clause = self._where_clause(ref.reference, ref.rrev, ref.pkgid, ref.prev)
        query = f'SELECT {self.columns.path} FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query)
        row = r.fetchone()
        if not row:
            raise ReferencesDbTable.DoesNotExist(
                f"No entry for reference '{ref.full_reference}'")
        return row[0]

    def save(self, conn: sqlite3.Cursor, path, ref) -> int:
        timestamp = int(time.time())
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        r = conn.execute(f'INSERT INTO {self.table_name} '
                         f'VALUES ({placeholders})',
                         [ref.reference, ref.rrev, ref.pkgid, ref.prev, path, timestamp])
        return r.lastrowid

    def update(self, conn: sqlite3.Cursor, pk: int, path=None, reference=None,
               rrev=None, pkgid=None, prev=None):
        timestamp = int(time.time())  # TODO: TBD: I will update the revision here too
        set_clause, set_values = self._set_clause(reference=reference, rrev=rrev, pkgid=pkgid,
                                                  prev=prev, path=path, timestamp=timestamp)
        query = f"UPDATE {self.table_name} " \
                f"SET {set_clause} " \
                f"WHERE rowid = ?;"
        r = conn.execute(query, (*set_values, pk))
        return r.lastrowid

    def update_path_ref(self, conn: sqlite3.Cursor, pk: int, new_path):
        timestamp = int(time.time())  # TODO: TBD: I will update the revision here too
        setters = ', '.join([f"{it} = ?" for it in ("path", "timestamp")])
        query = f"UPDATE {self.table_name} " \
                f"SET {setters} " \
                f"WHERE rowid = ?;"
        r = conn.execute(query, [new_path, timestamp, pk])
        return r.lastrowid

    def pk(self, conn: sqlite3.Cursor, ref):
        """ Returns the row matching the reference or fails """
        where_clause = self._where_clause(ref.reference, ref.rrev, ref.pkgid, ref.prev)
        query = f'SELECT rowid, * FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query)
        row = r.fetchone()
        if not row:
            raise ReferencesDbTable.DoesNotExist(
                f"No entry for reference '{ref.full_reference}'")
        return row

    def get(self, conn: sqlite3.Cursor, pk: int) -> ConanFileReference:
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE rowid = ?;'
        r = conn.execute(query, [pk, ])
        row = r.fetchone()
        return self._as_ref(self.row_type(*row))

    def filter(self, conn: sqlite3.Cursor, pattern: str,
               only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        """ Returns the references that match a given pattern (sql style) """
        if only_latest_rrev:
            query = f'SELECT DISTINCT {self.columns.reference}, ' \
                    f'                {self.columns.rrev}, MAX({self.columns.timestamp}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference} LIKE ? ' \
                    f'GROUP BY {self.columns.reference} ' \
                    f'ORDER BY MAX({self.columns.timestamp}) ASC'
        else:
            query = f'SELECT * FROM {self.table_name} ' \
                    f'WHERE {self.columns.reference} LIKE ?;'
        r = conn.execute(query, [pattern, ])
        for row in r.fetchall():
            yield self._as_ref(self.row_type(*row))

    def all(self, conn: sqlite3.Cursor, only_latest_rrev: bool) -> List[ConanFileReference]:
        if only_latest_rrev:
            query = f'SELECT DISTINCT {self.columns.reference}, ' \
                    f'                {self.columns.rrev}, MAX({self.columns.timestamp}) ' \
                    f'FROM {self.table_name} ' \
                    f'WHERE {self.columns.prev} IS NULL ' \
                    f'GROUP BY {self.columns.reference} ' \
                    f'ORDER BY MAX({self.columns.timestamp}) ASC'
        else:
            query = f'SELECT * FROM {self.table_name} WHERE {self.columns.prev} IS NULL;'
        r = conn.execute(query)
        for row in r.fetchall():
            yield self._as_ref(self.row_type(*row))

    def latest_rrev(self, conn: sqlite3.Cursor, ref: ConanFileReference) -> ConanFileReference:
        """ Returns the latest ref according to rrev """
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE {self.columns.reference} = ? ' \
                f'ORDER BY {self.columns.rrev} ' \
                f'LIMIT 1;'
        r = conn.execute(query, [str(ref), ])
        row = r.fetchone()
        return self._as_ref(self.row_type(*row))
