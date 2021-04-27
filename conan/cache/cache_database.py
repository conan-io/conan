import sqlite3
from contextlib import contextmanager
from io import StringIO
from typing import Tuple, Iterator

from conans.model.ref import ConanFileReference, PackageReference
from .db.references import ReferencesDbTable

CONNECTION_TIMEOUT_SECONDS = 1  # Time a connection will wait when the database is locked


class CacheDatabase:
    """ Abstracts the operations with the database and ensures they run sequentially """
    _references = ReferencesDbTable()

    timeout = CONNECTION_TIMEOUT_SECONDS

    def __init__(self, filename: str):
        self._filename = filename

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self._filename, isolation_level=None, timeout=self.timeout)
        try:
            conn.execute('begin EXCLUSIVE')
            yield conn.cursor()
            conn.execute("commit")
        finally:
            conn.close()

    def initialize(self, if_not_exists=True):
        with self.connect() as conn:
            self._references.create_table(conn, if_not_exists)

    def dump(self, output: StringIO):
        with self.connect() as conn:
            output.write(f"\nReferencesDbTable (table '{self._references.table_name}'):\n")
            self._references.dump(conn, output)

    def update_reference_revision(self, old_ref: ConanFileReference, new_ref: ConanFileReference):
        """ Assigns a revision 'new_ref.revision' to the reference given by 'old_ref' """
        with self.connect() as conn:
            ref_pk = self._references.pk(conn, str(old_ref), old_ref.revision, None, None)
            try:
                self._references.update(conn, ref_pk, str(new_ref), new_ref.revision, None, None)
            except sqlite3.IntegrityError:
                raise ReferencesDbTable.AlreadyExist(f"Reference '{new_ref.full_str()}' already exists")

    def update_reference_directory(self, path, reference, rrev, pkgid, prev):
        with self.connect() as conn:
            self._references.update_path_ref(conn, path, reference, rrev, pkgid, prev)

    def try_get_reference_directory(self, reference, rrev, pkgid, prev):
        """ Returns the directory where the given reference is stored (or fails) """
        with self.connect() as conn:
            return self._references.get_path_ref(conn, reference, rrev, pkgid, prev)

    def get_or_create_reference(self, path, reference, rrev, pkgid, prev) -> Tuple[str, bool]:
        """ Returns the path for the given reference. If the reference doesn't exist in the
            database, it will create the entry for the reference using the path given as argument.
        """
        with self.connect() as conn:
            try:
                return self._references.get_path_ref(conn, reference, rrev, pkgid, prev), False
            except ReferencesDbTable.DoesNotExist:
                self._references.save(conn, path, reference, rrev, pkgid, prev)
                return path, True

    def list_references(self, only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        with self.connect() as conn:
            for it in self._references.all(conn, only_latest_rrev):
                yield it
