import os
import sqlite3

from conan.api.output import ConanOutput
from conan.internal.cache.db.packages_table import PackagesDBTable
from conan.internal.cache.db.recipes_table import RecipesDBTable
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.model.version import Version


class CacheDatabase:

    def __init__(self, filename):
        version = sqlite3.sqlite_version
        if Version(version) < "3.7.11":
            ConanOutput().error(f"Your sqlite3 '{version} < 3.7.11' version is not supported")
        self._recipes = RecipesDBTable(filename)
        self._packages = PackagesDBTable(filename)
        if not os.path.isfile(filename):
            self._recipes.create_table()
            self._packages.create_table()

    def exists_prev(self, ref):
        # TODO: This logic could be done directly against DB
        matching_prevs = self.get_package_revisions_references(ref)
        return len(matching_prevs) > 0

    def get_latest_package_reference(self, ref):
        prevs = self.get_package_revisions_references(ref, True)
        return prevs[0] if prevs else None

    def update_recipe_timestamp(self, ref):
        self._recipes.update_timestamp(ref)

    def update_package_timestamp(self, pref: PkgReference, path: str, build_id: str):
        self._packages.update_timestamp(pref, path=path, build_id=build_id)

    def get_recipe_lru(self, ref):
        return self._recipes.get_recipe(ref)["lru"]

    def get_package_lru(self, pref: PkgReference):
        return self._packages.get(pref)["lru"]

    def update_recipe_lru(self, ref):
        self._recipes.update_lru(ref)

    def update_package_lru(self, pref):
        self._packages.update_lru(pref)

    def remove_recipe(self, ref: RecipeReference):
        # Removing the recipe must remove all the package binaries too from DB
        self._recipes.remove(ref)
        self._packages.remove_recipe(ref)

    def remove_package(self, ref: PkgReference):
        # Removing the recipe must remove all the package binaries too from DB
        self._packages.remove(ref)

    def remove_build_id(self, pref):
        self._packages.remove_build_id(pref)

    def get_matching_build_id(self, ref, build_id):
        # TODO: This can also be done in a single query in DB
        for d in self._packages.get_package_references(ref):
            existing_build_id = d["build_id"]
            if existing_build_id == build_id:
                return d["pref"]
        return None

    def get_recipe(self, ref: RecipeReference):
        """ Returns the reference data as a dictionary (or fails) """
        return self._recipes.get_recipe(ref)

    def get_latest_recipe(self, ref: RecipeReference):
        """ Returns the reference data as a dictionary (or fails) """
        return self._recipes.get_latest_recipe(ref)

    def get_recipe_revisions_references(self, ref: RecipeReference):
        return self._recipes.get_recipe_revisions_references(ref)

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
