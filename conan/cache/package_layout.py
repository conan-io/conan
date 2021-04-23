import os
import uuid

from conan.cache.cache import DataCache
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import PackageReference
from conans.paths import BUILD_FOLDER, PACKAGES_FOLDER


class PackageLayout(LockableMixin):
    _random_prev = False

    def __init__(self, pref: PackageReference, cache: DataCache, package_folder: str, locked=True,
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
        def get_build_directory():
            with self.lock(blocking=False):
                return os.path.join(self._cache.base_folder, BUILD_FOLDER)
        return get_build_directory()

    def package(self):
        def get_package_directory():
            with self.lock(blocking=False):
                return os.path.join(self._cache.base_folder, PACKAGES_FOLDER)
        return get_package_directory()
