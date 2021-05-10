import os

from conan.cache.cache import DataCache
from conan.cache.conan_reference import ConanReference
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
        super().__init__(resource=self._pref.full_reference, **kwargs)

    def assign_prev(self, pref: ConanReference):
        assert pref.reference == self._pref.reference, "You cannot change the reference here"
        assert not self._locked, "You can only change it if it was not assigned at the beginning"
        assert pref.prev, "It only makes sense to change if you are providing a revision"
        new_resource: str = pref.full_reference

        with self.exchange(new_resource):
            # Assign the new revision
            old_pref = self._pref
            self._pref = pref
            self._random_prev = False

            # Reassign PACKAGE folder in the database (BUILD is not moved)
            new_directory = self._cache._move_prev(old_pref, self._pref)
            if new_directory:
                self._package_folder = new_directory

    def build(self):
        return os.path.join(self._cache.base_folder, self._package_folder, BUILD_FOLDER)

    def package(self):
        return os.path.join(self._cache.base_folder, self._package_folder, PACKAGES_FOLDER)

    def base_directory(self):
        return os.path.join(self._cache.base_folder, self._package_folder)

    def download_package(self):
        return os.path.join(self._cache.base_folder, self._package_folder, "dl", "pkg")
