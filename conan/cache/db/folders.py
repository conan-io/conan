import sqlite3
import time
from enum import Enum, unique
from typing import Optional

from conan.cache.db.table import BaseDbTable
from conans.model.ref import ConanFileReference, PackageReference
from conans.errors import ConanException
from .packages import PackagesDbTable
from .references import ReferencesDbTable


@unique
class ConanFolders(Enum):
    REFERENCE = 0
    PKG_BUILD = 1
    PKG_PACKAGE = 2


class FoldersDbTable(BaseDbTable):
    table_name = 'conan_paths'
    columns_description = [('reference_pk', int),
                           ('package_pk', int, True),
                           ('path', str, False, None, True),  # TODO: Add unittest
                           ('folder', int, False, [it.value for it in ConanFolders]),
                           ('last_modified', int)]
    # TODO: Add unittest
    # TODO: Check if the fact that path is not unique (several references that share the
    #  same rrev will share the same folder in the cache is the desired behaviour)
    unique_together = ('reference_pk', 'package_pk', 'folder')
    references: ReferencesDbTable = None
    packages: PackagesDbTable = None

    class DoesNotExist(ConanException):
        pass

    class MultipleObjectsReturned(ConanException):
        pass

    class AlreadyExist(ConanException):
        pass

    def create_table(self, conn: sqlite3.Cursor, references: ReferencesDbTable, packages: PackagesDbTable,
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

    """
    Functions to touch (update) the timestamp of given entries
    """

    def _touch(self, conn: sqlite3.Cursor, rowid: int):
        timestamp = int(time.time())
        query = f"UPDATE {self.table_name} " \
                f"SET {self.columns.last_modified} = ? " \
                f"WHERE rowid = {rowid}"
        r = conn.execute(query, [timestamp, ])
        assert r.rowcount == 1

    def touch_ref(self, conn: sqlite3.Cursor, ref: ConanFileReference):
        timestamp = int(time.time())
        ref_pk = self.references.pk(conn, ref)
        query = f"UPDATE {self.table_name} " \
                f"SET {self.columns.last_modified} = ? " \
                f'WHERE {self.columns.reference_pk} = ? AND {self.columns.package_pk} IS NULL;'
        r = conn.execute(query, [timestamp, ref_pk, ])
        assert r.rowcount == 1

    def touch_pref(self, conn: sqlite3.Cursor, pref: PackageReference):
        """ Touching a pref implies touching the reference """
        timestamp = int(time.time())
        pref_pk = self.packages.pk(conn, pref)
        query = f"UPDATE {self.table_name} " \
                f"SET {self.columns.last_modified} = ? " \
                f'WHERE {self.columns.package_pk} = ?;'
        r = conn.execute(query, [timestamp, pref_pk, ])
        assert r.rowcount >= 1
        self.touch_ref(conn, pref.ref)

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
        if not row:
            raise FoldersDbTable.DoesNotExist(f"No entry folder for reference '{ref.full_str()}'")
        self._touch(conn, row[0])  # Update LRU timestamp (only the reference)
        return row[1]

    def update_path_ref(self, conn: sqlite3.Cursor, ref: ConanFileReference, path: str):
        """ Updates the value of the path assigned to given reference """
        ref_pk = self.references.pk(conn, ref)
        query = f'UPDATE {self.table_name} ' \
                f'SET {self.columns.path} = ? ' \
                f'WHERE {self.columns.reference_pk} = ? AND {self.columns.package_pk} IS NULL;'
        r = conn.execute(query, [path, ref_pk, ])
        return r.lastrowid

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
        if not row:
            raise FoldersDbTable.DoesNotExist(f"No entry folder for package reference '{pref.full_str()}'")
        # Update LRU timestamp (the package and the reference)
        self._touch(conn, row[0])
        self.touch_ref(conn, pref.ref)
        return row[1]

    def update_path_pref(self, conn: sqlite3.Cursor, pref: ConanFileReference, path: str,
                         folder: ConanFolders):
        """ Updates the value of the path assigned to given package reference and folder-type """
        ref_pk = self.references.pk(conn, pref.ref)
        pref_pk = self.packages.pk(conn, pref)
        query = f'UPDATE {self.table_name} ' \
                f'SET {self.columns.path} = ? ' \
                f'WHERE {self.columns.reference_pk} = ? AND {self.columns.package_pk} = ?' \
                f'       AND {self.columns.folder} = ?;'
        r = conn.execute(query, [path, ref_pk, pref_pk, folder.value, ])
        return r.lastrowid

    def get_lru_ref(self, conn: sqlite3.Cursor, timestamp: int):
        """ Returns references not used after given 'timestamp' """
        query = f'SELECT {self.columns.reference_pk} FROM {self.table_name} ' \
                f'WHERE {self.columns.package_pk} IS NULL AND {self.columns.last_modified} < ?;'
        r = conn.execute(query, [timestamp, ])
        for row in r.fetchall():
            yield self.references.get(conn, row[0])

    def get_lru_pref(self, conn: sqlite3.Cursor, timestamp: int):
        """ Returns packages not used after given 'timestamp' """
        query = f'SELECT DISTINCT {self.columns.package_pk} FROM {self.table_name} ' \
                f'WHERE {self.columns.package_pk} IS NOT NULL AND {self.columns.last_modified} < ?;'
        r = conn.execute(query, [timestamp, ])
        for row in r.fetchall():
            yield self.packages.get(conn, row[0])
