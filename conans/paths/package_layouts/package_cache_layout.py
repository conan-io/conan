# coding=utf-8

import os
import platform
import threading
from contextlib import contextmanager

import fasteners

from conans.client.tools.oss import OSInfo
from conans.errors import NotFoundException, ConanException
from conans.errors import RecipeNotFoundException, PackageNotFoundException
from conans.model.manifest import FileTreeManifest
from conans.model.manifest import discarded_file
from conans.model.package_metadata import PackageMetadata
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference
from conans.util.env_reader import get_env
from conans.util.files import load, save, rmdir, set_dirty, clean_dirty, is_dirty
from conans.util.locks import Lock, NoLock, ReadLock, SimpleLock, WriteLock
from conans.util.log import logger


# TODO: cache2.0 remove this class, using as an adapter to pass tests from 2.0 that
#  use the package_layout directly
class PackageCacheLayout(object):
    """ This is the package layout for Conan cache """

    def __init__(self, ref, cache):
        assert isinstance(ref, ConanFileReference)
        self._ref = ref
        self._cache = cache

    @property
    def ref(self):
        return self._ref

    def ref_layout(self):
        latest_rrev = self._cache.get_latest_rrev(self._ref)
        return self._cache.get_ref_layout(latest_rrev)

    def pkg_layout(self, pref):
        latest_rrev = self._cache.get_latest_rrev(pref.ref)
        latest_prev = self._cache.get_latest_prev(PackageReference(latest_rrev, pref.id))
        return self._cache.get_pkg_layout(latest_prev)

    def base_folder(self):
        return self.ref_layout().base_folder

    def export(self):
        return self.ref_layout().export()

    def conanfile(self):
        return self.ref_layout().conanfile()

    def conandata(self):
        return self.ref_layout().conandata()

    def export_sources(self):
        return self.ref_layout().export_sources()

    def source(self):
        return self.ref_layout().source()

    def scm_sources(self):
        return self.ref_layout().scm_sources()

    def build(self, pref):
        return self.pkg_layout(pref).build()

    def system_reqs_package(self, pref):
        return self.pkg_layout(pref).system_reqs_package()

    def builds(self):
        latest_rrev = self._cache.get_latest_rrev(self._ref)
        package_ids = self._cache.get_package_ids(latest_rrev)
        build_folders = []
        for package_id in package_ids:
            prev = self._cache.get_latest_prev(package_id)
            build_folders.append(self._cache.get_pkg_layout(prev).build())
        return build_folders

    def packages(self):
        latest_rrev = self._cache.get_latest_rrev(self._ref)
        package_ids = self._cache.get_package_ids(latest_rrev)
        packages_folders = []
        for package_id in package_ids:
            prev = self._cache.get_latest_prev(package_id)
            packages_folders.append(self._cache.get_pkg_layout(prev).package())
        return packages_folders

    def package(self, pref):
        return self.pkg_layout(pref).package()

    def download_package(self, pref):
        return self.pkg_layout(pref).download_package()

    def download_export(self):
        return self.ref_layout().download_export()

    def package_is_dirty(self, pref):
        raise ConanException("package_is_dirty moved to cache2.0")

    def package_id_exists(self, package_id):
        raise ConanException("cache2.0: package_id_exists removed")

    def package_remove(self, pref):
        raise ConanException("cache2.0: package_remove removed")

    def sources_remove(self):
        raise ConanException("cache2.0: sources_remove removed")

    def export_remove(self):
        raise ConanException("cache2.0: export_remove removed")

    def package_metadata(self):
        raise ConanException("cache2.0: package_metadata removed")

    def recipe_manifest(self):
        return FileTreeManifest.load(self.export())

    def package_manifests(self, pref):
        package_folder = self.package(pref)
        readed_manifest = FileTreeManifest.load(package_folder)
        expected_manifest = FileTreeManifest.create(package_folder)
        return readed_manifest, expected_manifest

    def package_exists(self, pref):
        # used only for Remover, to check if package_id provided by users exists
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        return (self.recipe_exists() and
                os.path.exists(self.package(pref)) and
                (not pref.revision or self.package_revision(pref) == pref.revision))

    def recipe_revision(self):
        return self.ref_layout().reference.revision

    def package_revision(self, pref):
        return self.pkg_layout(pref).reference.revision

    def conan_builds(self):
        builds_dir = self.builds()
        try:
            builds = [dirname for dirname in os.listdir(builds_dir)
                      if os.path.isdir(os.path.join(builds_dir, dirname))]
        except OSError:  # if there isn't any package folder
            builds = []
        return builds

    def package_ids(self):
        """ get a list of all package_ids for this recipe
        """
        latest_rrev = self._cache.get_latest_rrev(self._ref)
        packages = self._cache.get_package_ids(latest_rrev)
        return [package.id for package in packages]

    # Metadata
    def load_metadata(self):
        raise ConanException("cache2.0: metadata does not exist in 2.0")

    @contextmanager
    def update_metadata(self):
        raise ConanException("cache2.0: metadata does not exist in 2.0")

    # Locks
    def conanfile_read_lock(self, output):
        if self._no_lock:
            return NoLock()
        return ReadLock(self._base_folder, self._ref, output)

    def conanfile_write_lock(self, output):
        if self._no_lock:
            return NoLock()
        return WriteLock(self._base_folder, self._ref, output)

    def conanfile_lock_files(self, output):
        if self._no_lock:
            return ()
        return WriteLock(self._base_folder, self._ref, output).files

    def package_lock(self, pref):
        if self._no_lock:
            return NoLock()
        return SimpleLock(os.path.join(self._base_folder, "locks", pref.id))

    def remove_package_locks(self):
        conan_folder = self._base_folder
        Lock.clean(conan_folder)
        rmdir(os.path.join(conan_folder, "locks"))

    # Raw access to file
    def get_path(self, path, package_id=None):
        """ Return the contents for the given `path` inside current layout, it can
            be a single file or the list of files in a directory

            :param package_id: will retrieve the contents from the package directory
            :param path: path relative to the cache reference or package folder
        """

        assert not os.path.isabs(path)

        if package_id is None:  # Get the file in the exported files
            folder = self.export()
        else:
            pref = PackageReference(self._ref, package_id)
            folder = self.package(pref)

        abs_path = os.path.join(folder, path)
        if not os.path.exists(abs_path):
            raise NotFoundException("The specified path doesn't exist")
        if os.path.isdir(abs_path):
            keep_python = get_env("CONAN_KEEP_PYTHON_FILES", False)
            return sorted([path for path in os.listdir(abs_path) if not discarded_file(path,
                                                                                       keep_python)])
        else:
            return load(abs_path)
