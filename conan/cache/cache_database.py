import sqlite3

from conans.model.ref import ConanFileReference, PackageReference


class CacheDatabase:
    _column_ref = 'reference'
    _column_rrev = 'rrev'
    _column_pkgid = 'pkgid'
    _column_prev = 'prev'
    _column_config = 'config'

    def __init__(self, filename: str):
        # We won't run out of file descriptors, so implementation here is up to the threading
        # model decided for Conan
        self._conn = sqlite3.connect(filename)

    def create_table(self, if_not_exists: bool = True):
        guard = 'IF NOT EXISTS' if if_not_exists else ''
        query = f"""
        CREATE TABLE {guard} {self._table_name} (
            {self._column_resource} text NOT NULL,
            {self._column_pid} integer NOT NULL,
            {self._column_writer} BOOLEAN NOT NULL CHECK ({self._column_writer} IN (0,1))
        );
        """
        with self._conn:
            self._conn.execute(query)


    def get_directory(self, ref: ConanFileReference):
        reference = ref.full_str()
        # TODO: We can encode here
