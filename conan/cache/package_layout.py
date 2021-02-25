import os
import uuid

from conan.cache.cache import Cache
from conan.cache.cache_database_directories import ConanFolders
from conan.cache.cache_folder import CacheFolder
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import PackageReference
from conan.cache.recipe_layout import RecipeLayout


class PackageLayout(LockableMixin):
    _random_prev = False

    def __init__(self, recipe_layout: RecipeLayout, pref: PackageReference, cache: Cache,
                 **kwargs):
        self._recipe_layout = recipe_layout
        self._pref = pref
        if not self._pref.revision:
            self._random_prev = True
            self._pref = pref.copy_with_revs(pref.ref.revision, str(uuid.uuid4()))
        self._cache = cache

        # Get paths for this package revision
        package_path = self._cache._backend.get_default_package_path(pref, ConanFolders.PKG_PACKAGE)
        self._package_path = \
            self._cache._backend.get_or_create_package_directory(self._pref,
                                                                 ConanFolders.PKG_PACKAGE,
                                                                 package_path)
        build_path = self._cache._backend.get_default_package_path(pref, ConanFolders.PKG_BUILD)
        self._build_path = \
            self._cache._backend.get_or_create_package_directory(self._pref, ConanFolders.PKG_BUILD,
                                                                 build_path)

        resource_id = self._pref.full_str()
        super().__init__(resource=resource_id, **kwargs)

    def assign_prev(self, pref: PackageReference, move_contents: bool = False):
        assert pref.ref.full_str() == self._pref.ref.full_str(), "You cannot change the reference here"
        assert self._random_prev, "You can only change it if it was not assigned at the beginning"
        assert pref.revision, "It only makes sense to change if you are providing a revision"
        new_resource: str = pref.full_str()

        with self.exchange(new_resource):
            # Assign the new revision
            old_pref = self._pref
            self._pref = pref
            self._random_prev = False

            # Reassign PACKAGE folder in the database (BUILD is not moved)
            new_directory = self._cache._move_prev(old_pref, self._pref, ConanFolders.PKG_PACKAGE,
                                                   move_contents)
            if new_directory:
                self._package_path = new_directory

    @property
    def base_directory(self):
        with self.lock(blocking=False):
            return os.path.join(self._cache.base_folder, self._base_directory)

    def build(self):
        """ Returns the 'build' folder. Here we would need to deal with different situations:
            * temporary folder (to be removed after used)
            * persistent folder
            * deterministic folder (forced from outside)
        """

        def get_build_directory():
            with self.lock(blocking=False):
                return os.path.join(self._cache.base_folder, self._build_path)

        build_directory = lambda: get_build_directory()
        return CacheFolder(build_directory, False, manager=self._manager, resource=self._resource)

    def package(self):
        """ We want this folder to be deterministic, although the final location is not known
            until we have the package revision... so it has to be updated!
        """

        def get_package_directory():
            with self.lock(blocking=False):
                return os.path.join(self._cache.base_folder, self._package_path)

        package_directory = lambda: get_package_directory()
        return CacheFolder(package_directory, True, manager=self._manager, resource=self._resource)
