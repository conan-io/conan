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
from conans.paths import CONANFILE, SYSTEM_REQS, EXPORT_FOLDER, EXPORT_SRC_FOLDER, SRC_FOLDER, \
    BUILD_FOLDER, PACKAGES_FOLDER, SYSTEM_REQS_FOLDER, PACKAGE_METADATA, SCM_SRC_FOLDER, DATA_YML, \
    rm_conandir
from conans.util.env_reader import get_env
from conans.util.files import load, save, rmdir, set_dirty, clean_dirty, is_dirty
from conans.util.locks import Lock, NoLock, ReadLock, SimpleLock, WriteLock
from conans.util.log import logger


def short_path(func):
    if platform.system() == "Windows" or OSInfo().is_cygwin:  # Not for other subsystems
        from conans.util.windows import path_shortener

        def wrap(self, *args, **kwargs):
            p = func(self, *args, **kwargs)
            return path_shortener(p, self._short_paths)

        return wrap
    else:
        return func


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

    @property
    def ref_layout(self):
        latest_rrev = self._cache.get_latest_rrev(self._ref)
        return self._cache.get_ref_layout(latest_rrev)

    @property
    def pkg_layout(self):
        latest_rrev = self._cache.get_latest_rrev(self._ref)
        latest_prev = self._cache.get_latest_rrev(latest_rrev)
        return self._cache.get_pkg_layout(latest_prev)

    def base_folder(self):
        return self.ref_layout.base_folder

    def export(self):
        return self.ref_layout.export()

    def conanfile(self):
        return self.ref_layout.conanfile()

    def conandata(self):
        return self.ref_layout.conandata()

    @short_path
    def export_sources(self):
        return self.ref_layout.export_sources()

    @short_path
    def source(self):
        return self.ref_layout.source()

    @short_path
    def scm_sources(self):
        return self.ref_layout.scm_sources()

    def builds(self):
        return self.pkg_layout.build()

    @short_path
    def build(self, pref):
        return self.pkg_layout.build()

    def system_reqs(self):
        return self.pkg_layout.system_reqs()

    def system_reqs_package(self, pref):
        return self.pkg_layout.system_reqs_package()

    def remove_system_reqs(self):
        system_reqs_folder = os.path.join(self._base_folder, SYSTEM_REQS_FOLDER)
        if not os.path.exists(self._base_folder):
            raise ValueError("%s does not exist" % repr(self._ref))
        if not os.path.exists(system_reqs_folder):
            return
        try:
            rmdir(system_reqs_folder)
        except Exception as e:
            raise ConanException("Unable to remove system requirements at %s: %s"
                                 % (system_reqs_folder, str(e)))

    def packages(self):
        return self.pkg_layout.package()

    def package(self, pref):
        return self.pkg_layout.package()

    @contextmanager
    def set_dirty_context_manager(self, pref):
        raise("set_dirty_context_manager moved to cache2.0")

    def download_package(self, pref):
        return self.pkg_layout.download_package()

    def download_export(self):
        return self.ref_layout.download_export()

    def package_is_dirty(self, pref):
        raise ConanException("package_is_dirty moved to cache2.0")

    def package_id_exists(self, package_id):
        raise ConanException("cache2.0: package_id_exists removed")

    def package_remove(self, pref):
        raise ConanException("cache2.0: package_id_exists removed")

    def sources_remove(self):
        raise ConanException("cache2.0: package_id_exists removed")

    def export_remove(self):
        raise ConanException("cache2.0: package_id_exists removed")

    def package_metadata(self):
        raise ConanException("cache2.0: package_id_exists removed")

    def recipe_manifest(self):
        return FileTreeManifest.load(self.export())

    def package_manifests(self, pref):
        package_folder = self.package(pref)
        readed_manifest = FileTreeManifest.load(package_folder)
        expected_manifest = FileTreeManifest.create(package_folder)
        return readed_manifest, expected_manifest

    def recipe_exists(self):
        return os.path.exists(self.export()) and \
               (not self._ref.revision or self.recipe_revision() == self._ref.revision)

    def package_exists(self, pref):
        # used only for Remover, to check if package_id provided by users exists
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        return (self.recipe_exists() and
                os.path.exists(self.package(pref)) and
                (not pref.revision or self.package_revision(pref) == pref.revision))

    def recipe_revision(self):
        metadata = self.load_metadata()
        return metadata.recipe.revision

    def package_revision(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref.copy_clear_rev() == self._ref.copy_clear_rev()
        metadata = self.load_metadata()
        if pref.id not in metadata.packages:
            raise PackageNotFoundException(pref)
        return metadata.packages[pref.id].revision

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
        packages_dir = self.packages()
        try:
            packages = [dirname for dirname in os.listdir(packages_dir)
                        if os.path.isdir(os.path.join(packages_dir, dirname))]
        except OSError:  # if there isn't any package folder
            packages = []
        return packages

    # Metadata
    def load_metadata(self):
        try:
            text = load(self.package_metadata())
        except IOError:
            raise RecipeNotFoundException(self._ref)
        return PackageMetadata.loads(text)

    _metadata_locks = {}  # Needs to be shared among all instances

    @contextmanager
    def update_metadata(self):
        metadata_path = self.package_metadata()
        lockfile = metadata_path + ".lock"
        with fasteners.InterProcessLock(lockfile, logger=logger):
            lock_name = self.package_metadata()  # The path is the thing that defines mutex
            thread_lock = PackageCacheLayout._metadata_locks.setdefault(lock_name, threading.Lock())
            thread_lock.acquire()
            try:
                try:
                    metadata = self.load_metadata()
                except RecipeNotFoundException:
                    metadata = PackageMetadata()
                yield metadata
                save(metadata_path, metadata.dumps())
            finally:
                thread_lock.release()

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
