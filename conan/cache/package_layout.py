import os
from contextlib import contextmanager

from conan.cache.cache import DataCache
from conan.cache.conan_reference import ConanReference
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference
from conans.paths import BUILD_FOLDER, PACKAGES_FOLDER, SYSTEM_REQS_FOLDER, SYSTEM_REQS, rm_conandir
from conans.util.files import rmdir, set_dirty, clean_dirty, is_dirty


# TODO: cache2.0 create an unique layout class
class PackageLayout:
    def __init__(self, pref: ConanReference, cache: DataCache, package_folder: str):
        self._pref = pref
        self._cache = cache
        self._package_folder = package_folder

    @property
    def reference(self):
        return self._pref

    def assign_prev(self, pref: ConanReference):
        assert pref.reference == self._pref.reference, "You cannot change the reference here"
        assert pref.prev, "It only makes sense to change if you are providing a revision"

        # TODO: here maybe we should block
        # Assign the new revision
        old_pref = self._pref
        self._pref = pref

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

    # TODO: cache2.0 fix this
    def system_reqs(self):
        return os.path.join(self._cache.base_folder, SYSTEM_REQS_FOLDER, SYSTEM_REQS)

    # TODO: cache2.0 fix this
    def system_reqs_package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.id == self._pref.pkgid
        assert pref.ref.revision == self._pref.rrev
        return os.path.join(self._cache.base_folder, SYSTEM_REQS_FOLDER, pref.id, SYSTEM_REQS)

    # TODO: cache2.0 locks
    def package_remove(self):
        # Here we could validate and check we own a write lock over this package
        tgz_folder = self.download_package()
        rmdir(tgz_folder)
        try:
            rmdir(self.package())
        except OSError as e:
            raise ConanException("%s\n\nFolder: %s\n"
                                 "Couldn't remove folder, might be busy or open\n"
                                 "Close any app using it, and retry" % (self.package(), str(e)))

    def package_manifests(self):
        package_folder = self.package()
        readed_manifest = FileTreeManifest.load(package_folder)
        expected_manifest = FileTreeManifest.create(package_folder)
        return readed_manifest, expected_manifest

    def get_remote(self):
        return self._cache.get_remote(self._pref)

    # TODO: cache2.0 check this
    @contextmanager
    def set_dirty_context_manager(self):
        set_dirty(self.package())
        yield
        clean_dirty(self.package())

    # TODO: cache2.0 check this
    def package_is_dirty(self):
        return is_dirty(self.package())
