import time
import uuid
from enum import Enum, unique
from io import StringIO
from typing import Tuple, Union

from conan.cache.exceptions import DuplicateReferenceException, DuplicatePackageReferenceException
from conan.utils.sqlite3 import Sqlite3MemoryMixin, Sqlite3FilesystemMixin
from conans.model.ref import ConanFileReference, PackageReference


@unique
class ConanFolders(Enum):
    REFERENCE = 0
    PKG_BUILD = 1
    PKG_PACKAGE = 2


class CacheDatabase:
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

    def get_or_create_directory(self, item: Union[ConanFileReference, PackageReference],
                                default_path: str = None) -> Tuple[str, bool]:
        # reference = str(ref)
        # assert reference, "Empty reference cannot get into the cache"
        # assert not pref or ref == pref.ref, "Both parameters should belong to the same reference"

        # Search the database
        where_clause, where_values = self._where_clause(item, filter_packages=True)
        query = f'SELECT {self._column_path} ' \
                f'FROM {self._table_name} ' \
                f'WHERE {where_clause};'

        with self.connect() as conn:
            r = conn.execute(query, where_values)
            rows = r.fetchall()
            assert len(rows) <= 1, f"Unique entry expected... found {rows}," \
                                   f" for where clause {where_clause}"  # TODO: Ensure this uniqueness
            if not rows:
                path = default_path or self._get_random_directory(item)
                ref = item if isinstance(item, ConanFileReference) else item.ref
                pref = item if isinstance(item, PackageReference) else None
                values = (str(ref),
                          ref.name,
                          ref.revision if ref.revision else None,
                          pref.id if pref else None,
                          pref.revision if pref and pref.revision else None,
                          path,
                          ConanFolders.REFERENCE.value,
                          int(time.time()))
                conn.execute(f'INSERT INTO {self._table_name} '
                             f'VALUES (?, ?, ?, ?, ?, ?, ?, ?)', values)
                return path, True
            else:
                return rows[0][0], False

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

            where_clause, where_values = self._where_clause(old_pref, filter_packages=True)
            query = f"UPDATE {self._table_name} " \
                    f"SET {self._column_prev} = '{new_pref.revision}' " \
                    f"WHERE {where_clause}"
            r = conn.execute(query, where_values)
            assert r.rowcount > 0

    def update_path(self, item: Union[ConanFileReference, PackageReference], new_path: str):
        where_clause, where_values = self._where_clause(item, filter_packages=True)
        query = f"UPDATE {self._table_name} " \
                f"SET    {self._column_path} = '{new_path}' " \
                f"WHERE {where_clause}"
        with self.connect() as conn:
            r = conn.execute(query, where_values)
            assert r.rowcount > 0


class CacheDatabaseSqlite3Memory(CacheDatabase, Sqlite3MemoryMixin):
    pass


class CacheDatabaseSqlite3Filesystem(CacheDatabase, Sqlite3FilesystemMixin):
    pass
