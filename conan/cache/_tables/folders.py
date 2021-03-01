import sqlite3
import time
from enum import Enum, unique
from typing import Optional

from conan.cache._tables.base_table import BaseTable
from conans.model.ref import ConanFileReference, PackageReference
from .packages import Packages
from .references import References


@unique
class ConanFolders(Enum):
    REFERENCE = 0
    PKG_BUILD = 1
    PKG_PACKAGE = 2


class Folders(BaseTable):
    table_name = 'conan_paths'
    columns_description = [('reference_pk', int),
                           ('package_pk', int, True),
                           ('path', str),
                           ('folder', int, False, [it.value for it in ConanFolders]),
                           ('last_modified', int)]

    # TODO: Add uniqueness constraints

    references: References = None
    packages: Packages = None

    def create_table(self, conn: sqlite3.Cursor, references: References, packages: Packages,
                     if_not_exists: bool = True):
        super().create_table(conn, if_not_exists)
        self.references = references
        self.packages = packages

    def _as_tuple(self, conn: sqlite3.Cursor, ref: ConanFileReference,
                  pref: Optional[PackageReference], path: str, folder: ConanFolders,
                  last_modified: int):
        assert not pref or pref.ref == ref, "Reference and pkg-reference must be the same"
        reference_pk = self.references.pk(conn, ref)
        package_pk = self.packages.pk(conn, pref) if pref else None
        return self.row_type(reference_pk=reference_pk, package_pk=package_pk, path=path,
                             folder=folder.value, last_modified=last_modified)

    def _touch(self, conn: sqlite3.Cursor, rowid: int):
        timestamp = int(time.time())
        query = f"UPDATE {self.table_name} " \
                f"SET {self.columns.last_modified} = ? " \
                f"WHERE rowid = {rowid}"
        r = conn.execute(query, [timestamp, ])
        assert r.rowcount > 0

    """
    Functions to manage the data in this table using Conan types
    """

    def save_ref(self, conn: sqlite3.Cursor, ref: ConanFileReference, path: str):
        timestamp = int(time.time())
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        r = conn.execute(f'INSERT INTO {self.table_name} '
                         f'VALUES ({placeholders})',
                         list(self._as_tuple(conn, ref, None, path, ConanFolders.REFERENCE,
                                             timestamp)))
        return r.lastrowid

    def save_pref(self, conn: sqlite3.Cursor, pref: PackageReference, path: str,
                  folder: ConanFolders):
        timestamp = int(time.time())
        placeholders = ', '.join(['?' for _ in range(len(self.columns))])
        r = conn.execute(f'INSERT INTO {self.table_name} '
                         f'VALUES ({placeholders})',
                         list(self._as_tuple(conn, pref.ref, pref, path, folder, timestamp)))
        return r.lastrowid

    def get_path_ref(self, conn: sqlite3.Cursor, ref: ConanFileReference) -> str:
        """ Returns and touches (updates LRU) the path for the given reference """
        ref_pk = self.references.pk(conn, ref)
        query = f'SELECT rowid, {self.columns.path} FROM {self.table_name} ' \
                f'WHERE {self.columns.reference_pk} = ? AND {self.columns.package_pk} IS NULL;'
        r = conn.execute(query, [ref_pk, ])
        row = r.fetchone()
        # TODO: Raise if not exists
        self._touch(conn, row[0])  # Update LRU timestamp
        return row[1]

    def get_path_pref(self, conn: sqlite3.Cursor, pref: PackageReference,
                      folder: ConanFolders) -> str:
        """ Returns and touches (updates LRU) the path for the given package reference """
        ref_pk = self.references.pk(conn, pref.ref)
        pref_pk = self.packages.pk(conn, pref)
        query = f'SELECT rowid, {self.columns.path} FROM {self.table_name} ' \
                f'WHERE {self.columns.reference_pk} = ? AND {self.columns.package_pk} = ?' \
                f'       AND {self.columns.folder} = ?;'
        r = conn.execute(query, [ref_pk, pref_pk, folder.value, ])
        row = r.fetchone()
        # TODO: Raise if not exists
        self._touch(conn, row[0])  # Update LRU timestamp
        return row[1]
