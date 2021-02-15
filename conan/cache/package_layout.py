import os
import uuid

from conan.cache.cache_folder import CacheFolder
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import PackageReference


class PackageLayout(LockableMixin):
    _random_prev = False

    def __init__(self, recipe_layout: 'RecipeLayout', pref: PackageReference, cache: 'Cache',
                 **kwargs):
        self._recipe_layout = recipe_layout
        self._pref = pref
        if not self._pref.revision:
            self._random_prev = True
            self._pref = pref.copy_with_revs(pref.ref.revision, uuid.uuid4())
        self._cache = cache

        #
        default_path = self._cache.get_default_path(pref)
        reference_path, _ = self._cache._backend.get_or_create_directory(self._pref.ref, self._pref,
                                                                         default_path=default_path)
        self._base_directory = reference_path
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

            # Reassign folder in the database
            new_directory = self._cache._move_prev(old_pref, self._pref, move_contents)
            if new_directory:
                self._base_directory = new_directory

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
        build_directory = lambda: os.path.join(self.base_directory, 'build')
        return CacheFolder(build_directory, False, manager=self._manager, resource=self._resource)

    def package(self):
        """ We want this folder to be deterministic, although the final location is not known
            until we have the package revision... so it has to be updated!
        """
        package_directory = lambda: os.path.join(self.base_directory, 'package')
        return CacheFolder(package_directory, True, manager=self._manager, resource=self._resource)
