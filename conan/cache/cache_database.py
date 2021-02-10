import sqlite3
import uuid
from typing import Tuple

from conans.model.ref import ConanFileReference, PackageReference


class CacheDatabase:
    _table_name = "conan_cache_directories"
    _column_ref = 'reference'
    _column_ref_name = 'reference_name'
    _column_rrev = 'rrev'
    _column_pkgid = 'pkgid'
    _column_prev = 'prev'
    _column_path = 'relpath'

    def __init__(self, filename: str):
        # We won't run out of file descriptors, so implementation here is up to the threading
        # model decided for Conan
        self._conn = sqlite3.connect(filename)

    def create_table(self, if_not_exists: bool = True):
        guard = 'IF NOT EXISTS' if if_not_exists else ''
        query = f"""
        CREATE TABLE {guard} {self._table_name} (
            {self._column_ref} text NOT NULL,
            {self._column_ref_name} text NOT NULL,
            {self._column_rrev} text,
            {self._column_pkgid} text,
            {self._column_prev} text,
            {self._column_path} text NOT NULL
        );
        """
        # TODO: Need to add some timestamp for LRU removal
        with self._conn:
            self._conn.execute(query)

    def dump(self):
        with self._conn:
            r = self._conn.execute(f'SELECT * FROM {self._table_name}')
            for it in r.fetchall():
                print(it)

    def _get_random_directory(self, ref: ConanFileReference = None,
                              pref: PackageReference = None) -> str:
        # TODO: We could implement deterministic output for some inputs, not now.
        # TODO: If we are creating the 'path' here, we need the base_folder (and lock depending on implementation)
        return str(uuid.uuid4())

    def _where_clause(self, ref: ConanFileReference, pref: PackageReference = None,
                      filter_packages: bool = True):
        assert filter_packages or not pref, "It makes no sense to NOT filter by packages when they are explicit"
        reference = str(ref)
        where_clauses = {
            self._column_ref: f"'{reference}'",
            self._column_rrev: f"'{ref.revision}'" if ref.revision else 'null',
        }
        if filter_packages:
            where_clauses.update({
                self._column_pkgid: f"'{pref.id}'" if pref else 'null',
                self._column_prev: f"'{pref.revision}'" if pref and pref.revision else 'null'
            })
        cmp_expr = lambda k, v: f'{k} = {v}' if v != 'null' else f'{k} IS {v}'
        where_expr = ' AND '.join([cmp_expr(k, v) for k, v in where_clauses.items()])
        return where_expr

    def get_or_create_directory(self, ref: ConanFileReference, pref: PackageReference = None,
                                default_path: str = None) -> Tuple[str, bool]:
        reference = str(ref)
        assert reference, "Empty reference cannot get into the cache"
        assert not pref or ref == pref.ref, "Both parameters should belong to the same reference"

        # Search the database
        where_clause = self._where_clause(ref, pref, filter_packages=True)
        query = f'SELECT {self._column_path} ' \
                f'FROM {self._table_name} ' \
                f'WHERE {where_clause}'

        with self._conn:
            r = self._conn.execute(query)
            rows = r.fetchall()
            assert len(rows) <= 1, f"Unique entry expected... found {rows}," \
                                   f" for where clause {where_clause}"  # TODO: Ensure this uniqueness
            if not rows:
                path = default_path or self._get_random_directory(ref, pref)
                values = [f'"{reference}"',
                          f'"{ref.name}"',
                          f'"{ref.revision}"' if ref.revision else 'NULL',
                          f'"{pref.id}"' if pref else 'NULL',
                          f'"{pref.revision}"' if pref and pref.revision else 'NULL',
                          f'"{path}"'
                          ]
                self._conn.execute(f'INSERT INTO {self._table_name} '
                                   f'VALUES ({", ".join(values)})')
                return path, True
            else:
                return rows[0][0], False

    def update_rrev(self, old_ref: ConanFileReference, new_ref: ConanFileReference):
        query = f"UPDATE {self._table_name} " \
                f"SET {self._column_rrev} = '{new_ref.revision}' " \
                f"WHERE {self._where_clause(old_ref, filter_packages=False)}"
        with self._conn:
            # Check if the new_ref already exists, if not, we can move the old_one
            query_exists = f'SELECT EXISTS(SELECT 1 ' \
                           f'FROM {self._table_name} ' \
                           f'WHERE {self._where_clause(new_ref, filter_packages=False)})'
            r = self._conn.execute(query_exists)
            if r.fetchone()[0] == 1:
                raise Exception('Pretended reference already exists')

            r = self._conn.execute(query)
            assert r.rowcount > 0

    def update_prev(self, old_pref: PackageReference, new_pref: PackageReference):
        query = f"UPDATE {self._table_name} " \
                f"SET {self._column_prev} = '{new_pref.revision}' " \
                f"WHERE {self._where_clause(ref=old_pref.ref, pref=old_pref)}"
        with self._conn:
            # Check if the new_pref already exists, if not, we can move the old_one
            query_exists = f'SELECT EXISTS(SELECT 1 ' \
                           f'FROM {self._table_name} ' \
                           f'WHERE {self._where_clause(new_pref.ref, new_pref, filter_packages=True)})'
            r = self._conn.execute(query_exists)
            if r.fetchone()[0] == 1:
                raise Exception('Pretended prev already exists')

            r = self._conn.execute(query)
            assert r.rowcount > 0

    def update_path(self, ref: ConanFileReference, new_path: str, pref: PackageReference = None):
        query = f"UPDATE {self._table_name} " \
                f"SET    {self._column_path} = '{new_path}' " \
                f"WHERE {self._where_clause(ref, pref)}"
        with self._conn:
            r = self._conn.execute(query)
            assert r.rowcount > 0


