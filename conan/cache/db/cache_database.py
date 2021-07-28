import sqlite3
from io import StringIO

from conan.cache.conan_reference import ConanReference
from conan.cache.db.references import ReferencesDbTable

CONNECTION_TIMEOUT_SECONDS = 1  # Time a connection will wait when the database is locked


class CacheDatabase:

    def __init__(self, filename):
        self._conn = sqlite3.connect(filename, isolation_level=None,
                                     timeout=CONNECTION_TIMEOUT_SECONDS, check_same_thread=False)
        self._references = ReferencesDbTable(self._conn)

    def close(self):
        self._conn.close()

    def dump(self, output: StringIO):
        output.write(f"\nReferencesDbTable (table '{self._references.table_name}'):\n")
        self._references.dump(output)

    def update_reference(self, old_ref: ConanReference, new_ref: ConanReference = None,
                         new_path=None, new_remote=None, new_build_id=None):
        self._references.update(old_ref, new_ref, new_path, new_remote, new_build_id)

    def delete_ref_by_path(self, path):
        self._references.delete_by_path(path)

    def remove(self, ref: ConanReference):
        self._references.remove(ref)

    def try_get_reference_directory(self, ref: ConanReference):
        """ Returns the directory where the given reference is stored (or fails) """
        ref_data = self._references.get(ref)
        return ref_data["path"]

    def create_tmp_reference(self, path, ref: ConanReference):
        self._references.save(path, ref, reset_timestamp=True)

    def create_reference(self, path, ref: ConanReference):
        self._references.save(path, ref)

    def list_references(self, only_latest_rrev):
        for it in self._references.all(only_latest_rrev):
            yield it

    def get_package_revisions(self, ref: ConanReference, only_latest_prev=False):
        for it in self._references.get_package_revisions(ref, only_latest_prev):
            yield it

    def get_package_ids(self, ref: ConanReference):
        for it in self._references.get_package_ids(ref):
            yield it

    def get_build_id(self, ref: ConanReference):
        return self._references.get_build_id(ref)

    def get_recipe_revisions(self, ref: ConanReference, only_latest_rrev=False):
        for it in self._references.get_recipe_revisions(ref, only_latest_rrev):
            yield it

    def get_remote(self, ref: ConanReference):
        return self._references.get_remote(ref)

    def set_remote(self, ref: ConanReference, remote):
        return self._references.set_remote(ref, remote)

    def get_timestamp(self, ref: ConanReference):
        return self._references.get_timestamp(ref)
