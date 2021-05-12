import os

from conan.cache.cache import DataCache
from conan.cache.conan_reference import ConanReference
from conans.model.ref import PackageReference
from conans.paths import BUILD_FOLDER, PACKAGES_FOLDER


class PackageLayout:
    _random_prev = False

    def __init__(self, pref: PackageReference, cache: DataCache, package_folder: str):
        self._pref = pref
        self._cache = cache
        self._package_folder = package_folder

    def assign_prev(self, pref: ConanReference):
        assert pref.reference == self._pref.reference, "You cannot change the reference here"
        assert pref.prev, "It only makes sense to change if you are providing a revision"

        # TODO: here maybe we should block
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
