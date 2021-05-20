import sqlite3
from contextlib import contextmanager
from io import StringIO
from typing import Tuple, Iterator

from conans.model.ref import ConanFileReference
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

    def update_reference(self, old_ref, new_ref=None, new_path=None, new_remote=None):
        with self.connect() as conn:
            try:
                self._references.update(conn, old_ref, new_ref, new_path, new_remote)
            except sqlite3.IntegrityError:
                raise ReferencesDbTable.AlreadyExist(
                    f"Reference '{new_ref.full_reference}' already exists")

    def delete_ref_by_path(self, path):
        with self.connect() as conn:
            self._references.delete_by_path(conn, path)

    def remove(self, ref):
        with self.connect() as conn:
            self._references.remove(conn, ref)

    def try_get_reference_directory(self, ref):
        """ Returns the directory where the given reference is stored (or fails) """
        with self.connect() as conn:
            return self._references.get_path_ref(conn, ref)

    def get_or_create_reference(self, path, ref) -> Tuple[str, bool]:
        """ Returns the path for the given reference. If the reference doesn't exist in the
            database, it will create the entry for the reference using the path given as argument.
        """
        with self.connect() as conn:
            try:
                return self._references.get_path_ref(conn, ref), False
            except ReferencesDbTable.DoesNotExist:
                self._references.save(conn, path, ref)
                return path, True

    def list_references(self, only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        with self.connect() as conn:
            for it in self._references.all(conn, only_latest_rrev):
                yield it

    def get_package_revisions(self, ref, only_latest_prev=False):
        with self.connect() as conn:
            for it in self._references.get_prevs(conn, ref, only_latest_prev):
                yield it

    def get_package_ids(self, ref, only_latest_prev=False):
        with self.connect() as conn:
            for it in self._references.get_pkgids(conn, ref, only_latest_prev):
                yield it

    def get_recipe_revisions(self, ref, only_latest_rrev=False):
        with self.connect() as conn:
            for it in self._references.get_rrevs(conn, ref, only_latest_rrev):
                yield it

    def get_remote(self, ref):
        with self.connect() as conn:
            return self._references.get_remote(conn, ref)
