import os

from cache.cache_folder import CacheFolder
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import PackageReference


class PackageLayout(LockableMixin):

    def __init__(self, recipe_layout: 'RecipeLayout', pref: PackageReference, base_package_directory: str, cache: 'Cache', **kwargs):
        self._recipe_layout = recipe_layout
        self._pref = pref
        self._base_directory = base_package_directory
        self._cache = cache
        resource_id = pref.full_str()
        super().__init__(resource=resource_id, **kwargs)

        package_directory = os.path.join(self._base_directory, 'package')
        self._package_directory = CacheFolder(package_directory, True, manager=self._manager,
                                              resource=self._resource)

    def build(self):
        """ Returns the 'build' folder. Here we would need to deal with different situations:
            * temporary folder (to be removed after used)
            * persistent folder
            * deterministic folder (forced from outside)
        """
        build_directory = os.path.join(self._base_directory, 'build')
        return CacheFolder(build_directory, False, manager=self._manager, resource=self._resource)

    def package(self):
        """ We want this folder to be deterministic, although the final location is not known
            until we have the package revision... so it has to be updated!
        """
        return self._package_directory
