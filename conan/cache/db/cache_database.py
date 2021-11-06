import sqlite3
import time

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

    def update_recipe_timestamp(self, ref: ConanReference, new_timestamp=None):
        self._recipes.update_timestamp(ref, new_timestamp)

    def update_package_timestamp(self, ref: ConanReference, new_timestamp=None):
        self._packages.update_timestamp(ref,  new_timestamp)

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

    def create_recipe(self, path, ref: ConanReference):
        self._recipes.create(path, ref, timestamp=time.time())

    def create_package(self, path, ref: ConanReference, build_id):
        self._packages.create(path, ref, timestamp=time.time(), build_id=build_id)

    def list_references(self, only_latest_rrev):
        for it in self._recipes.all_references(only_latest_rrev):
            yield it

    def get_package_revisions(self, ref: ConanReference, only_latest_prev=False):
        for it in self._packages.get_package_revisions(ref, only_latest_prev):
            yield it

    def get_package_references(self, ref: ConanReference):
        for it in self._packages.get_package_references(ref):
            yield it

    def get_recipe_revisions(self, ref: ConanReference, only_latest_rrev=False):
        for it in self._recipes.get_recipe_revisions(ref, only_latest_rrev):
            yield it
