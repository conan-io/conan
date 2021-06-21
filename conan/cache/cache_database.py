import sqlite3
from contextlib import contextmanager
from io import StringIO

from .conan_reference import ConanReference
from .db.references import ReferencesDbTable

CONNECTION_TIMEOUT_SECONDS = 1  # Time a connection will wait when the database is locked


class CacheDatabase:

    timeout = CONNECTION_TIMEOUT_SECONDS

    def __init__(self, filename):
        self._filename = filename
        self._references = ReferencesDbTable()
        self._conn = sqlite3.connect(self._filename, isolation_level=None, timeout=self.timeout,
                                     check_same_thread=False)

    @contextmanager
    def connection(self):
        yield self._conn.cursor()

    def close(self):
        self._conn.close()

    def initialize(self, if_not_exists=True):
        with self.connection() as conn:
            self._references.create_table(conn, if_not_exists)

    def dump(self, output: StringIO):
        with self.connection() as conn:
            output.write(f"\nReferencesDbTable (table '{self._references.table_name}'):\n")
            self._references.dump(conn, output)

    def update_reference(self, old_ref: ConanReference, new_ref: ConanReference = None,
                         new_path=None, new_remote=None, new_build_id=None):
        with self.connection() as conn:
            try:
                self._references.update(conn, old_ref, new_ref, new_path, new_remote, new_build_id)
            except sqlite3.IntegrityError:
                raise ReferencesDbTable.AlreadyExist(
                    f"Reference '{new_ref.full_reference}' already exists")

    def delete_ref_by_path(self, path):
        with self.connection() as conn:
            self._references.delete_by_path(conn, path)

    def remove(self, ref: ConanReference):
        with self.connection() as conn:
            self._references.remove(conn, ref)

    def try_get_reference_directory(self, ref: ConanReference):
        """ Returns the directory where the given reference is stored (or fails) """
        with self.connection() as conn:
            ref_data = self._references.get(conn, ref)
            return ref_data["path"]

    def get_or_create_reference(self, path, ref: ConanReference):
        """ Returns the path for the given reference. If the reference doesn't exist in the
            database, it will create the entry for the reference using the path given as argument.
        """
        with self.connection() as conn:
            try:
                ref_data = self._references.get(conn, ref)
                return ref_data["path"], False
            except ReferencesDbTable.DoesNotExist:
                self._references.save(conn, path, ref)
                return path, True

    def list_references(self, only_latest_rrev):
        with self.connection() as conn:
            for it in self._references.all(conn, only_latest_rrev):
                yield it

    def get_package_revisions(self, ref: ConanReference, only_latest_prev=False, with_build_id=None):
        with self.connection() as conn:
            for it in self._references.get_prevs(conn, ref, only_latest_prev, with_build_id):
                yield it

    def get_package_ids(self, ref: ConanReference, only_latest_prev=False, with_build_id=None):
        with self.connection() as conn:
            for it in self._references.get_pkgids(conn, ref, only_latest_prev, with_build_id):
                yield it

    def get_recipe_revisions(self, ref: ConanReference, only_latest_rrev=False):
        with self.connection() as conn:
            for it in self._references.get_rrevs(conn, ref, only_latest_rrev):
                yield it

    def get_remote(self, ref: ConanReference):
        with self.connection() as conn:
            return self._references.get_remote(conn, ref)

    def set_remote(self, ref: ConanReference, remote):
        with self.connection() as conn:
            return self._references.set_remote(conn, ref, remote)

    def get_timestamp(self, ref: ConanReference):
        with self.connection() as conn:
            return self._references.get_timestamp(conn, ref)
