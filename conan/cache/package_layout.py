import os

from cache.cache_folder import CacheFolder
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import PackageReference, ConanFileReference


class PackageLayout(LockableMixin):

    def __init__(self, recipe_layout: 'RecipeLayout', pref: PackageReference,
                 base_package_directory: str, cache: 'Cache', **kwargs):
        self._recipe_layout = recipe_layout
        self._pref = pref
        self._base_directory = base_package_directory
        self._cache = cache
        resource_id = pref.full_str()
        super().__init__(resource=resource_id, **kwargs)

    def _assign_rrev(self, ref: ConanFileReference):
        new_pref = self._pref.copy_with_revs(ref.revision, p_revision=None)
        new_resource_id = new_pref.full_str()
        with self.exchange(new_resource_id):
            self._pref = new_pref
            # Nothing to move. Without package_revision the final location is not known yet.

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
        self._package_directory = CacheFolder(package_directory, True, manager=self._manager,
                                              resource=self._resource)
