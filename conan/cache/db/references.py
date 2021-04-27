import sqlite3
import time
from collections import namedtuple
from typing import Tuple, List, Iterator

from conan.cache.db.table import BaseDbTable
from conans.model.ref import ConanFileReference, PackageReference
from conans.errors import ConanException


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
        where = {
            self.columns.reference: reference,
            self.columns.rrev: rrev,
            self.columns.pkgid: pkgid or "NULL",
            self.columns.prev: prev or "NULL",
        }
        where_expr = ' AND '.join([f'{k} = ?' for k, v in where.items()])
        return where_expr, tuple(where.values())

    def get_path_ref(self, conn: sqlite3.Cursor, reference, rrev, pkgid, prev) -> str:
        """ Returns the row matching the reference or fails """
        where_clause, where_values = self._where_clause(reference, rrev, pkgid, prev)
        query = f'SELECT {self.columns.path} FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query, where_values)
        row = r.fetchone()
        if not row:
            raise ReferencesDbTable.DoesNotExist(f"No entry for reference '{reference}#{rrev}:{pkgid}#{prev}'")
        return row[0]

    def save(self, conn: sqlite3.Cursor, path, reference, rrev, pkgid, prev) -> int:
        timestamp = int(time.time())
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        pkgid = pkgid or 'NULL'
        prev = prev or 'NULL'
        r = conn.execute(f'INSERT INTO {self.table_name} '
                         f'VALUES ({placeholders})', [reference, rrev, pkgid, prev, path, timestamp])
        return r.lastrowid

    def update(self, conn: sqlite3.Cursor, pk: int, reference, rrev, pkgid, prev):
        """ Updates row 'pk' with values from 'ref' """
        timestamp = int(time.time())  # TODO: TBD: I will update the revision here too
        setters = ', '.join([f"{it} = ?" for it in self.columns])
        query = f"UPDATE {self.table_name} " \
                f"SET {setters} " \
                f"WHERE rowid = ?;"
        r = conn.execute(query, [reference, rrev, pkgid, prev, timestamp, pk])
        return r.lastrowid

    def pk(self, conn: sqlite3.Cursor, reference, rrev, pkgid, prev):
        """ Returns the row matching the reference or fails """
        where_clause, where_values = self._where_clause(reference, rrev, pkgid, prev)
        query = f'SELECT rowid FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query, where_values)
        row = r.fetchone()
        if not row:
            raise ReferencesDbTable.DoesNotExist(f"No entry for reference ''{reference}#{rrev}:{pkgid}#{prev}''")
        return row[0]

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
                    f'GROUP BY {self.columns.reference} ' \
                    f'ORDER BY MAX({self.columns.timestamp}) ASC'
        else:
            query = f'SELECT * FROM {self.table_name};'
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
