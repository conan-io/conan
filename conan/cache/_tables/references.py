import sqlite3
import time
from collections import namedtuple
from typing import Tuple, List

from conan.cache._tables.base_table import BaseTable
from conans.model.ref import ConanFileReference


class References(BaseTable):
    table_name = 'conan_references'
    columns_description = [('reference', str),
                           ('name', str),
                           ('rrev', str),
                           ('rrev_order', int)]

    # TODO: Add unique constraint for (reference, rrev)

    def _as_tuple(self, ref: ConanFileReference, rrev_order: int):
        return self.row_type(reference=str(ref), name=ref.name, rrev=ref.revision,
                             rrev_order=rrev_order)

    def _as_ref(self, row: namedtuple):
        return ConanFileReference.loads(f'{row.reference}#{row.rrev}', validate=False)

    def _where_clause(self, ref: ConanFileReference) -> Tuple[str, Tuple]:
        where = {
            self.columns.reference: str(ref),
            self.columns.rrev: ref.revision
        }
        where_expr = ' AND '.join([f'{k} = ?' for k, v in where.items()])
        return where_expr, tuple(where.values())

    """
    Functions to manage the data in this table using Conan types
    """

    def save(self, conn: sqlite3.Cursor, ref: ConanFileReference):
        timestamp = int(time.time())
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        r = conn.execute(f'INSERT INTO {self.table_name} '
                         f'VALUES ({placeholders})', list(self._as_tuple(ref, timestamp)))
        return r.lastrowid

    def pk(self, conn: sqlite3.Cursor, ref: ConanFileReference) -> int:
        """ Returns the row matching the reference or fails """
        where_clause, where_values = self._where_clause(ref)
        query = f'SELECT rowid FROM {self.table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query, where_values)
        row = r.fetchone()
        # TODO: Raise some NotFoundException if failed
        return row[0]

    def get(self, conn: sqlite3.Cursor, pk: int) -> ConanFileReference:
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE rowid = ?;'
        r = conn.execute(query, [pk, ])
        row = r.fetchone()
        return self._as_ref(self.row_type(*row))

    def filter(self, conn: sqlite3.Cursor, pattern: str) -> List[ConanFileReference]:
        """ Returns the references that match a given pattern (sql style) """
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE {self.columns.reference} LIKE ?;'
        r = conn.execute(query, [pattern, ])
        for row in r.fetchall():
            yield self._as_ref(self.row_type(*row))

    def versions(self, conn: sqlite3.Cursor, name: str) -> List[ConanFileReference]:
        """ Returns the references that match a given pattern (sql style) """
        query = f'SELECT * FROM {self.table_name} ' \
                f'WHERE {self.columns.name} = ?;'
        r = conn.execute(query, [name, ])
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
