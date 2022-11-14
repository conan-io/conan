import sqlite3

from conan.internal.cache.db.packages_table import PackagesDBTable
from conan.internal.cache.db.recipes_table import RecipesDBTable
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference

CONNECTION_TIMEOUT_SECONDS = 1  # Time a connection will wait when the database is locked


class CacheDatabase:

    def __init__(self, filename):
        self._conn = sqlite3.connect(filename, isolation_level=None,
                                     timeout=CONNECTION_TIMEOUT_SECONDS, check_same_thread=False)
        self._recipes = RecipesDBTable(self._conn)
        self._packages = PackagesDBTable(self._conn)

    def close(self):
        self._conn.close()

    def exists_rrev(self, ref):
        # TODO: This logic could be done directly against DB
        matching_rrevs = self.get_recipe_revisions_references(ref)
        return len(matching_rrevs) > 0

    def exists_prev(self, ref):
        # TODO: This logic could be done directly against DB
        matching_prevs = self.get_package_revisions_references(ref)
        return len(matching_prevs) > 0

    def get_recipe_timestamp(self, ref):
        # TODO: Remove this once the ref contains the timestamp
        ref_data = self.try_get_recipe(ref)
        return ref_data["ref"].timestamp  # Must exist

    def get_package_timestamp(self, ref):
        ref_data = self.try_get_package(ref)
        return ref_data["pref"].timestamp

    def get_latest_recipe_reference(self, ref):
        # TODO: This logic could be done directly in DB
        rrevs = self.get_recipe_revisions_references(ref, True)
        return rrevs[0] if rrevs else None

    def get_latest_package_reference(self, ref):
        prevs = self.get_package_revisions_references(ref, True)
        return prevs[0] if prevs else None

    def update_recipe_timestamp(self, ref):
        self._recipes.update_timestamp(ref)

    def update_package_timestamp(self, pref: PkgReference):
        self._packages.update_timestamp(pref)

    def remove_recipe(self, ref: RecipeReference):
        # Removing the recipe must remove all the package binaries too from DB
        self._recipes.remove(ref)
        self._packages.remove_recipe(ref)

    def remove_package(self, ref: PkgReference):
        # Removing the recipe must remove all the package binaries too from DB
        self._packages.remove(ref)

    def get_matching_build_id(self, ref, build_id):
        # TODO: This can also be done in a single query in DB
        for d in self._packages.get_package_references(ref):
            existing_build_id = d["build_id"]
            if existing_build_id == build_id:
                return d["pref"]
        return None

    def try_get_recipe(self, ref: RecipeReference):
        """ Returns the reference data as a dictionary (or fails) """
        ref_data = self._recipes.get(ref)
        return ref_data

    def try_get_package(self, ref: PkgReference):
        """ Returns the reference data as a dictionary (or fails) """
        ref_data = self._packages.get(ref)
        return ref_data

    def create_recipe(self, path, ref: RecipeReference):
        self._recipes.create(path, ref)

    def create_package(self, path, ref: PkgReference, build_id):
        self._packages.create(path, ref, build_id=build_id)

    def list_references(self):
        return [d["ref"]
                for d in self._recipes.all_references()]

    def get_package_revisions_references(self, pref: PkgReference, only_latest_prev=False):
        return [d["pref"]
                for d in self._packages.get_package_revisions_references(pref, only_latest_prev)]

    def get_package_references(self, ref: RecipeReference, only_latest_prev=True):
        return [d["pref"]
                for d in self._packages.get_package_references(ref, only_latest_prev)]

    def get_recipe_revisions_references(self, ref: RecipeReference, only_latest_rrev=False):
        return [d["ref"]
                for d in self._recipes.get_recipe_revisions_references(ref, only_latest_rrev)]
