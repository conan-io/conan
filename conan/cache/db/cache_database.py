import sqlite3
import time
from io import StringIO

from conan.cache.conan_reference import ConanReference
from conan.cache.db.packages_table import PackagesDBTable
from conan.cache.db.recipes_table import RecipesDBTable

CONNECTION_TIMEOUT_SECONDS = 1  # Time a connection will wait when the database is locked


class CacheDatabase:

    def __init__(self, filename):
        self._conn = sqlite3.connect(filename, isolation_level=None,
                                     timeout=CONNECTION_TIMEOUT_SECONDS, check_same_thread=False)
        self._recipes = RecipesDBTable(self._conn)
        self._packages = PackagesDBTable(self._conn)

    def close(self):
        self._conn.close()

    def dump(self, output: StringIO):
        output.write(f"\nRecipesDbTable (table '{self._recipes.table_name}'):\n")
        self._recipes.dump(output)
        output.write(f"\nPackagesDbTable (table '{self._recipes.table_name}'):\n")
        self._packages.dump(output)

    def update_recipe(self, old_ref: ConanReference, new_ref: ConanReference = None,
                      new_path=None, new_timestamp=None):
        self._recipes.update(old_ref, new_ref, new_path, new_timestamp)

    def update_package(self, old_ref: ConanReference, new_ref: ConanReference = None,
                       new_path=None, new_timestamp=None):
        self._packages.update(old_ref, new_ref, new_path, new_timestamp)

    def delete_recipe_by_path(self, path):
        self._recipes.delete_by_path(path)

    def delete_package_by_path(self, path):
        self._recipes.delete_by_path(path)

    def remove_recipe(self, ref: ConanReference):
        # Removing the recipe must remove all the package binaries too from DB
        self._recipes.remove(ref)
        self._packages.remove(ref)

    def remove_package(self, ref: ConanReference):
        # Removing the recipe must remove all the package binaries too from DB
        self._packages.remove(ref)

    def try_get_recipe(self, ref: ConanReference):
        """ Returns the reference data as a dictionary (or fails) """
        ref_data = self._recipes.get(ref)
        return ref_data

    def try_get_package(self, ref: ConanReference):
        """ Returns the reference data as a dictionary (or fails) """
        ref_data = self._packages.get(ref)
        return ref_data

    def create_tmp_recipe(self, path, ref: ConanReference):
        self._recipes.save(path, ref, timestamp=0)

    def create_tmp_package(self, path, ref: ConanReference):
        self._packages.save(path, ref, timestamp=0)

    def create_recipe(self, path, ref: ConanReference):
        self._recipes.save(path, ref, timestamp=time.time())

    def create_package(self, path, ref: ConanReference):
        self._packages.save(path, ref, timestamp=time.time())

    def list_references(self, only_latest_rrev):
        for it in self._recipes.all_references(only_latest_rrev):
            yield it

    def get_package_revisions(self, ref: ConanReference, only_latest_prev=False):
        for it in self._packages.get_package_revisions(ref, only_latest_prev):
            yield it

    def get_package_ids(self, ref: ConanReference):
        for it in self._packages.get_package_ids(ref):
            yield it

    def get_recipe_revisions(self, ref: ConanReference, only_latest_rrev=False):
        for it in self._recipes.get_recipe_revisions(ref, only_latest_rrev):
            yield it
