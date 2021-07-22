import sqlite3
from contextlib import contextmanager
from io import StringIO

from conan.cache.conan_reference import ConanReference
from conan.cache.db.references import ReferencesDbTable
from conans.errors import ConanReferenceAlreadyExist

CONNECTION_TIMEOUT_SECONDS = 1  # Time a connection will wait when the database is locked


class CacheDatabase:

    def __init__(self, filename):
        self._references = ReferencesDbTable()
        self._conn = sqlite3.connect(filename, isolation_level=None,
                                     timeout=CONNECTION_TIMEOUT_SECONDS, check_same_thread=False)
        self._initialize(if_not_exists=True)

    @contextmanager
    def connection(self):
        yield self._conn.cursor()
        self._conn.commit()

    def close(self):
        self._conn.close()

    def _initialize(self, if_not_exists=True):
        with self.connection() as conn:
            self._references.create_table(conn, if_not_exists)

    def dump(self, output: StringIO):
        with self.connection() as conn:
            output.write(f"\nReferencesDbTable (table '{self._references.table_name}'):\n")
            self._references.dump(conn, output)

    def update_reference(self, old_ref: ConanReference, new_ref: ConanReference = None,
                         new_path=None, new_remote=None, new_timestamp=None, new_build_id=None):
        with self.connection() as conn:
            try:
                self._references.update(conn, old_ref, new_ref, new_path, new_remote, new_timestamp,
                                        new_build_id)
            except sqlite3.IntegrityError:
                raise ConanReferenceAlreadyExist(f"Reference '{new_ref.full_reference}' already exists")

    def delete_ref_by_path(self, path):
        with self.connection() as conn:
            self._references.delete_by_path(conn, path)

    def remove(self, ref: ConanReference):
        with self.connection() as conn:
            self._references.remove(conn, ref)

    def try_get_reference(self, ref: ConanReference):
        """ Returns the reference data as a dictionary (or fails) """
        with self.connection() as conn:
            ref_data = self._references.get(conn, ref)
            return ref_data

    def create_tmp_reference(self, path, ref: ConanReference):
        with self.connection() as conn:
            self._references.save(conn, path, ref, reset_timestamp=True)

    def create_reference(self, path, ref: ConanReference):
        with self.connection() as conn:
            self._references.save(conn, path, ref)

    def list_references(self, only_latest_rrev):
        with self.connection() as conn:
            for it in self._references.all(conn, only_latest_rrev):
                yield it

    def get_package_revisions(self, ref: ConanReference, only_latest_prev=False):
        with self.connection() as conn:
            for it in self._references.get_package_revisions(conn, ref, only_latest_prev):
                yield it

    def get_package_ids(self, ref: ConanReference):
        with self.connection() as conn:
            for it in self._references.get_package_ids(conn, ref):
                yield it

    def get_build_id(self, ref: ConanReference):
        with self.connection() as conn:
            return self._references.get_build_id(conn, ref)

    def get_recipe_revisions(self, ref: ConanReference, only_latest_rrev=False):
        with self.connection() as conn:
            for it in self._references.get_recipe_revisions(conn, ref, only_latest_rrev):
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
