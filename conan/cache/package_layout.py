import os
import uuid

from conan.cache.cache import Cache
from conan.cache.cache_folder import CacheFolder
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import PackageReference
from ._tables.folders import ConanFolders


class PackageLayout(LockableMixin):
    _random_prev = False

    def __init__(self, pref: PackageReference, cache: Cache, package_folder: str, locked=True,
                 **kwargs):
        self._pref = pref
        self._cache = cache
        self._locked = locked
        self._package_folder = package_folder
        super().__init__(resource=self._pref.full_str(), **kwargs)

    def assign_prev(self, pref: PackageReference, move_contents: bool = False):
        assert pref.ref.full_str() == self._pref.ref.full_str(), "You cannot change the reference here"
        assert not self._locked, "You can only change it if it was not assigned at the beginning"
        assert pref.revision, "It only makes sense to change if you are providing a revision"
        new_resource: str = pref.full_str()

        with self.exchange(new_resource):
            # Assign the new revision
            old_pref = self._pref
            self._pref = pref
            self._random_prev = False

            # Reassign PACKAGE folder in the database (BUILD is not moved)
            new_directory = self._cache._move_prev(old_pref, self._pref, move_contents)
            if new_directory:
                self._package_folder = new_directory

    def build(self):
        """ Returns the 'build' folder. Here we would need to deal with different situations:
            * temporary folder (to be removed after used)
            * persistent folder
            * deterministic folder (forced from outside)
        """

        def get_build_directory():
            with self.lock(blocking=False):
                build_folder = self._cache.db.get_or_create_package_reference_directory(
                    self._pref, str(uuid.uuid4()), ConanFolders.PKG_BUILD)
                return os.path.join(self._cache.base_folder, build_folder)

        build_directory = lambda: get_build_directory()
        return CacheFolder(build_directory, False, manager=self._manager, resource=self._resource)

    def package(self):
        """ We want this folder to be deterministic, although the final location is not known
            until we have the package revision... so it has to be updated!
        """

        def get_package_directory():
            with self.lock(blocking=False):
                return os.path.join(self._cache.base_folder, self._package_folder)

        package_directory = lambda: get_package_directory()
        return CacheFolder(package_directory, True, manager=self._manager, resource=self._resource)
