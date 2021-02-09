import sqlite3

from conans.model.ref import ConanFileReference, PackageReference
import uuid

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

    def _get_random_directory(self, ref: ConanFileReference = None, pref: PackageReference = None) -> str:
        # TODO: We could implement deterministic output for some inputs, not now.
        # TODO: If we are creating the 'path' here, we need the base_folder (and lock depending on implementation)
        return str(uuid.uuid4())

    def get_directory(self, ref: ConanFileReference, pref: PackageReference = None):
        reference = str(ref)
        assert reference, "Empty reference cannot get into the cache"
        assert not pref or ref == pref.ref, "Both parameters should belong to the same reference"

        # Search the database
        where_clauses = {self._column_ref: reference}
        if ref.revision:
            where_clauses[self._column_rrev] = ref.revision
        if pref:
            where_clauses[self._column_pkgid] = pref.id
            if pref.revision:
                where_clauses[self._column_prev] = pref.revision

        where_expr = ' AND '.join([f'{k} = "{v}"' for k, v in where_clauses.items()])
        query = f'SELECT {self._column_path} ' \
                f'FROM {self._table_name} ' \
                f'WHERE {where_expr}'

        with self._conn:
            r = self._conn.execute(query)
            rows = r.fetchall()
            assert len(rows) <= 1, "Unique entry expected..."  # TODO: Ensure this uniqueness
            if not rows:
                path = self._get_random_directory(ref, pref)
                values = [f'"{reference}"',
                          f'"{ref.name}"',
                          f'"{ref.revision}"' if ref.revision else 'null',
                          f'"{pref.id}"' if pref else 'null',
                          f'"{pref.revision}"' if pref and pref.revision else 'null',
                          f'"{path}"'
                          ]
                self._conn.execute(f'INSERT INTO {self._table_name} '
                                   f'VALUES ({", ".join(values)})')
            else:
                path = rows[0][0]
            return path
