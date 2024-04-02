import os
from typing import List

from conan.internal.cache.cache import DataCache, RecipeLayout, PackageLayout
from conans.client.store.localdb import LocalDB
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.files import mkdir

LOCALDB = ".conan.db"


# TODO: Rename this to ClientHome
class ClientCache(object):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands. Accesses to real disk and reads/write things. (OLD client ConanPaths)
    """

    def __init__(self, cache_folder, global_conf):
        self.cache_folder = cache_folder
        # paths
        self._store_folder = global_conf.get("core.cache:storage_path") or \
                             os.path.join(self.cache_folder, "p")

        try:
            mkdir(self._store_folder)
            db_filename = os.path.join(self._store_folder, 'cache.sqlite3')
            self._data_cache = DataCache(self._store_folder, db_filename)
        except Exception as e:
            raise ConanException(f"Couldn't initialize storage in {self._store_folder}: {e}")

    @property
    def temp_folder(self):
        """ temporary folder where Conan puts exports and packages before the final revision
        is computed"""
        # TODO: Improve the path definitions, this is very hardcoded
        return os.path.join(self._store_folder, "t")

    @property
    def builds_folder(self):
        return os.path.join(self._store_folder, "b")

    def create_export_recipe_layout(self, ref: RecipeReference):
        return self._data_cache.create_export_recipe_layout(ref)

    def assign_rrev(self, layout: RecipeLayout):
        return self._data_cache.assign_rrev(layout)

    def create_build_pkg_layout(self, ref):
        return self._data_cache.create_build_pkg_layout(ref)

    def assign_prev(self, layout: PackageLayout):
        return self._data_cache.assign_prev(layout)

    # Recipe methods
    def recipe_layout(self, ref: RecipeReference):
        return self._data_cache.get_recipe_layout(ref)

    def get_latest_recipe_reference(self, ref):
        # TODO: We keep this for testing only, to be removed
        assert ref.revision is None
        return self._data_cache.get_recipe_layout(ref).reference

    def get_recipe_revisions_references(self, ref):
        # For listing multiple revisions only
        assert ref.revision is None
        return self._data_cache.get_recipe_revisions_references(ref)

    def pkg_layout(self, ref: PkgReference):
        return self._data_cache.get_package_layout(ref)

    def get_or_create_ref_layout(self, ref: RecipeReference):
        return self._data_cache.get_or_create_ref_layout(ref)

    def get_or_create_pkg_layout(self, ref: PkgReference):
        return self._data_cache.get_or_create_pkg_layout(ref)

    def remove_recipe_layout(self, layout):
        self._data_cache.remove_recipe(layout)

    def remove_package_layout(self, layout):
        self._data_cache.remove_package(layout)

    def remove_build_id(self, pref):
        self._data_cache.remove_build_id(pref)

    def update_recipe_timestamp(self, ref):
        """ when the recipe already exists in cache, but we get a new timestamp from a server
        that would affect its order in our cache """
        return self._data_cache.update_recipe_timestamp(ref)

    def all_refs(self):
        return self._data_cache.list_references()

    def exists_prev(self, pref):
        # Used just by download to skip downloads if prev already exists in cache
        return self._data_cache.exists_prev(pref)

    def get_package_revisions_references(self, pref: PkgReference, only_latest_prev=False):
        return self._data_cache.get_package_revisions_references(pref, only_latest_prev)

    def get_package_references(self, ref: RecipeReference,
                               only_latest_prev=True) -> List[PkgReference]:
        """Get the latest package references"""
        return self._data_cache.get_package_references(ref, only_latest_prev)

    def get_matching_build_id(self, ref, build_id):
        return self._data_cache.get_matching_build_id(ref, build_id)

    def get_latest_package_reference(self, pref):
        return self._data_cache.get_latest_package_reference(pref)

    def get_recipe_lru(self, ref):
        return self._data_cache.get_recipe_lru(ref)

    def update_recipe_lru(self, ref):
        self._data_cache.update_recipe_lru(ref)

    def get_package_lru(self, pref):
        return self._data_cache.get_package_lru(pref)

    def update_package_lru(self, pref):
        self._data_cache.update_package_lru(pref)

    @property
    def store(self):
        return self._store_folder

    @property
    def localdb(self):
        localdb_filename = os.path.join(self.cache_folder, LOCALDB)
        return LocalDB(localdb_filename)
