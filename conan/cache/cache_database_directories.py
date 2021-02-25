import sqlite3
import time
import uuid
from enum import Enum, unique
from io import StringIO
from typing import Tuple, Union, Optional

from conan.cache.exceptions import DuplicateReferenceException, DuplicatePackageReferenceException, \
    CacheDirectoryNotFound, CacheDirectoryAlreadyExists
from conan.utils.sqlite3 import Sqlite3MemoryMixin, Sqlite3FilesystemMixin
from conans.model.ref import ConanFileReference, PackageReference


@unique
class ConanFolders(Enum):
    REFERENCE = 0
    PKG_BUILD = 1
    PKG_PACKAGE = 2


class CacheDatabaseDirectories:
    _table_name = "conan_cache_directories"
    _column_ref = 'reference'
    _column_ref_name = 'reference_name'
    _column_rrev = 'rrev'
    _column_pkgid = 'pkgid'
    _column_prev = 'prev'
    _column_path = 'relpath'
    _column_folder = 'folder'
    _column_last_modified = 'last_modified'

    def create_table(self, if_not_exists: bool = True):
        guard = 'IF NOT EXISTS' if if_not_exists else ''
        query = f"""
        CREATE TABLE {guard} {self._table_name} (
            {self._column_ref} text NOT NULL,
            {self._column_ref_name} text NOT NULL,
            {self._column_rrev} text,
            {self._column_pkgid} text,
            {self._column_prev} text,
            {self._column_path} text NOT NULL,
            {self._column_folder} integer NOT NULL CHECK ({self._column_folder} IN (0,1, 2)),
            {self._column_last_modified} integer NOT NULL
        );
        """
        # TODO: Need to add some timestamp for LRU removal
        with self.connect() as conn:
            conn.execute(query)

    def dump(self, output: StringIO):
        with self.connect() as conn:
            r = conn.execute(f'SELECT * FROM {self._table_name}')
            for it in r.fetchall():
                output.write(str(it) + '\n')

    def _get_random_directory(self, item: Union[ConanFileReference, PackageReference]) -> str:
        # TODO: We could implement deterministic output for some inputs, not now.
        # TODO: If we are creating the 'path' here, we need the base_folder (and lock depending on implementation)
        return str(uuid.uuid4())

    """
    Functions to filter the 'conan_cache_directories' table using a Conan reference or package-ref
    """

    def _where_reference_clause(self, ref: ConanFileReference, filter_packages: bool) -> dict:
        where_clauses = {
            self._column_ref: str(ref),
            self._column_rrev: ref.revision if ref.revision else None,
        }
        if filter_packages:
            where_clauses.update({
                self._column_pkgid: None,
                self._column_prev: None
            })
        return where_clauses

    def _where_package_reference_clause(self, pref: PackageReference) -> dict:
        where_clauses = self._where_reference_clause(pref.ref, False)
        where_clauses.update({
            self._column_pkgid: pref.id if pref else None,
            self._column_prev: pref.revision if pref and pref.revision else None
        })
        return where_clauses

    def _where_clause(self, item: Union[ConanFileReference, PackageReference],
                      filter_packages: bool) -> Tuple[str, Tuple]:
        if isinstance(item, ConanFileReference):
            where_clauses = self._where_reference_clause(item, filter_packages)
        else:
            assert filter_packages, 'If using PackageReference then it WILL filter by packages'
            where_clauses = self._where_package_reference_clause(item)

        def cmp_expr(k, v):
            return f'{k} = ?' if v is not None else f'{k} IS ?'

        where_expr = ' AND '.join([cmp_expr(k, v) for k, v in where_clauses.items()])
        where_values = tuple(where_clauses.values())
        return where_expr, where_values

    """
    Functions to retrieve and create entries in the database database.
    """

    def _try_get_reference_directory(self, item: ConanFileReference, conn: sqlite3.Cursor):
        where_clause, where_values = self._where_clause(item, filter_packages=True)
        query = f'SELECT {self._column_path} ' \
                f'FROM {self._table_name} ' \
                f'WHERE {where_clause};'
        r = conn.execute(query, where_values)
        rows = r.fetchall()
        assert len(rows) <= 1, f"Unique entry expected... found {rows}," \
                               f" for where clause {where_clause}"  # TODO: Ensure this uniqueness
        if not rows:
            raise CacheDirectoryNotFound(item)
        return rows[0][0]

    def _try_get_package_directory(self, item: PackageReference, folder: ConanFolders,
                                   conn: sqlite3.Cursor):
        where_clause, where_values = self._where_clause(item, filter_packages=True)
        query = f'SELECT {self._column_path} ' \
                f'FROM {self._table_name} ' \
                f'WHERE {where_clause} AND {self._column_folder} = ?;'
        where_values = where_values + (folder.value,)

        r = conn.execute(query, where_values)
        rows = r.fetchall()
        assert len(rows) <= 1, f"Unique entry expected... found {rows}," \
                               f" for where clause {where_clause}"  # TODO: Ensure this uniqueness
        if not rows:
            raise CacheDirectoryNotFound(item)
        return rows[0][0]

    def _create_reference_directory(self, ref: ConanFileReference, conn: sqlite3.Cursor,
                                    path: Optional[str] = None) -> str:
        # It doesn't exists, create the directory
        path = path or self._get_random_directory(ref)
        values = (str(ref),
                  ref.name,
                  ref.revision if ref.revision else None,
                  None,
                  None,
                  path,
                  ConanFolders.REFERENCE.value,
                  int(time.time()))
        r = conn.execute(f'INSERT INTO {self._table_name} '
                         f'VALUES (?, ?, ?, ?, ?, ?, ?, ?)', values)
        assert r.lastrowid  # FIXME: Check it has inserted something
        return path

    def _create_package_directory(self, pref: PackageReference, folder: ConanFolders,
                                  conn: sqlite3.Cursor, path: Optional[str] = None) -> str:
        # It doesn't exist, create the directory
        path = path or self._get_random_directory(pref)
        ref = pref.ref
        pref = pref
        values = (str(ref),
                  ref.name,
                  ref.revision,
                  pref.id,
                  pref.revision if pref.revision else None,
                  path,
                  folder.value,
                  int(time.time()))
        r = conn.execute(f'INSERT INTO {self._table_name} '
                         f'VALUES (?, ?, ?, ?, ?, ?, ?, ?)', values)
        assert r.lastrowid  # FIXME: Check it has inserted something
        return path

    def try_get_reference_directory(self, item: ConanFileReference):
        """ Returns the directory or fails """
        with self.connect() as conn:
            return self._try_get_reference_directory(item, conn)

    def try_get_package_directory(self, item: PackageReference, folder: ConanFolders):
        """ Returns the directory or fails """
        with self.connect() as conn:
            return self._try_get_package_directory(item, folder, conn)

    def create_reference_directory(self, ref: ConanFileReference, path: Optional[str] = None) -> str:
        with self.connect() as conn:
            try:
                self._try_get_reference_directory(ref, conn)
            except CacheDirectoryNotFound:
                return self._create_reference_directory(ref, conn, path)
            else:
                raise CacheDirectoryAlreadyExists(ref)

    def create_package_directory(self, pref: PackageReference, folder: ConanFolders,
                                 path: Optional[str] = None) -> str:
        with self.connect() as conn:
            try:
                self._try_get_package_directory(item=pref, folder=folder, conn=conn)
            except CacheDirectoryNotFound:
                return self._create_package_directory(pref, folder, conn, path)
            else:
                raise CacheDirectoryAlreadyExists(pref)

    def get_or_create_reference_directory(self, ref: ConanFileReference,
                                          path: Optional[str] = None) -> str:
        with self.connect() as conn:
            try:
                return self._try_get_reference_directory(ref, conn)
            except CacheDirectoryNotFound:
                return self._create_reference_directory(ref, conn, path)

    def get_or_create_package_directory(self, pref: PackageReference, folder: ConanFolders,
                                        path: Optional[str] = None) -> str:
        with self.connect() as conn:
            try:
                return self._try_get_package_directory(pref, folder, conn)
            except CacheDirectoryNotFound:
                return self._create_package_directory(pref, folder, conn, path)

    """
    Functions to update information already in the database: rrev, prev, paths,...
    """

    def update_rrev(self, old_ref: ConanFileReference, new_ref: ConanFileReference):
        with self.connect() as conn:
            # Check if the new_ref already exists, if not, we can move the old_one
            where_clause, where_values = self._where_clause(new_ref, filter_packages=False)
            query_exists = f'SELECT EXISTS(SELECT 1 ' \
                           f'FROM {self._table_name} ' \
                           f'WHERE {where_clause})'
            r = conn.execute(query_exists, where_values)
            if r.fetchone()[0] == 1:
                raise DuplicateReferenceException(new_ref)

            # TODO: Fix Sql injection here
            where_clause, where_values = self._where_clause(old_ref, filter_packages=False)
            query = f"UPDATE {self._table_name} " \
                    f"SET {self._column_rrev} = '{new_ref.revision}' " \
                    f"WHERE {where_clause}"
            r = conn.execute(query, where_values)
            assert r.rowcount > 0

    def update_prev(self, old_pref: PackageReference, new_pref: PackageReference):
        with self.connect() as conn:
            # Check if the new_pref already exists, if not, we can move the old_one
            where_clause, where_values = self._where_clause(new_pref, filter_packages=True)
            query_exists = f'SELECT EXISTS(SELECT 1 ' \
                           f'FROM {self._table_name} ' \
                           f'WHERE {where_clause})'
            r = conn.execute(query_exists, where_values)
            if r.fetchone()[0] == 1:
                raise DuplicatePackageReferenceException(new_pref)

            # TODO: Fix Sql injection here
            where_clause, where_values = self._where_clause(old_pref, filter_packages=True)
            query = f"UPDATE {self._table_name} " \
                    f"SET {self._column_prev} = '{new_pref.revision}' " \
                    f"WHERE {where_clause}"
            r = conn.execute(query, where_values)
            assert r.rowcount > 0

    def update_path(self, item: Union[ConanFileReference, PackageReference], new_path: str):
        where_clause, where_values = self._where_clause(item, filter_packages=True)
        # TODO: Fix Sql injection here
        query = f"UPDATE {self._table_name} " \
                f"SET    {self._column_path} = '{new_path}' " \
                f"WHERE {where_clause}"
        with self.connect() as conn:
            r = conn.execute(query, where_values)
            assert r.rowcount > 0


class CacheDatabaseDirectoriesSqlite3Memory(CacheDatabaseDirectories, Sqlite3MemoryMixin):
    pass


class CacheDatabaseDirectoriesSqlite3Filesystem(CacheDatabaseDirectories, Sqlite3FilesystemMixin):
    pass
