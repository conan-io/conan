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
    BUILD_FOLDER, PACKAGES_FOLDER, SYSTEM_REQS_FOLDER, PACKAGE_METADATA, SCM_SRC_FOLDER, rm_conandir
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


class PackageCacheLayout(object):
    """ This is the package layout for Conan cache """

    def __init__(self, base_folder, ref, short_paths, no_lock):
        assert isinstance(ref, ConanFileReference)
        self._ref = ref
        self._base_folder = os.path.normpath(base_folder)
        self._short_paths = short_paths
        self._no_lock = no_lock

    @property
    def ref(self):
        return self._ref

    def base_folder(self):
        """ Returns the base folder for this package reference """
        return self._base_folder

    def export(self):
        return os.path.join(self._base_folder, EXPORT_FOLDER)

    def conanfile(self):
        export = self.export()
        return os.path.join(export, CONANFILE)

    @short_path
    def export_sources(self):
        return os.path.join(self._base_folder, EXPORT_SRC_FOLDER)

    @short_path
    def source(self):
        return os.path.join(self._base_folder, SRC_FOLDER)

    @short_path
    def scm_sources(self):
        return os.path.join(self._base_folder, SCM_SRC_FOLDER)

    def builds(self):
        return os.path.join(self._base_folder, BUILD_FOLDER)

    @short_path
    def build(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        return os.path.join(self._base_folder, BUILD_FOLDER, pref.id)

    def system_reqs(self):
        return os.path.join(self._base_folder, SYSTEM_REQS_FOLDER, SYSTEM_REQS)

    def system_reqs_package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        return os.path.join(self._base_folder, SYSTEM_REQS_FOLDER, pref.id, SYSTEM_REQS)

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
        return os.path.join(self._base_folder, PACKAGES_FOLDER)

    @short_path
    def package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref, "{!r} != {!r}".format(pref.ref, self._ref)
        return os.path.join(self._base_folder, PACKAGES_FOLDER, pref.id)

    @contextmanager
    def set_dirty_context_manager(self, pref):
        pkg_folder = os.path.join(self._base_folder, PACKAGES_FOLDER, pref.id)
        set_dirty(pkg_folder)
        yield
        clean_dirty(pkg_folder)

    def download_package(self, pref):
        return os.path.join(self._base_folder, "dl", "pkg", pref.id)

    def download_export(self):
        return os.path.join(self._base_folder, "dl", "export")

    def package_is_dirty(self, pref):
        pkg_folder = os.path.join(self._base_folder, PACKAGES_FOLDER, pref.id)
        return is_dirty(pkg_folder)

    def package_id_exists(self, package_id):
        # The package exists if the folder exists, also for short_paths case
        pkg_folder = self.package(PackageReference(self._ref, package_id))
        return os.path.isdir(pkg_folder)

    def package_remove(self, pref):
        # Here we could validate and check we own a write lock over this package
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref, "{!r} != {!r}".format(pref.ref, self._ref)
        # Remove the tgz storage
        tgz_folder = self.download_package(pref)
        rmdir(tgz_folder)
        # This is NOT the short paths, but the standard cache one
        pkg_folder = os.path.join(self._base_folder, PACKAGES_FOLDER, pref.id)
        try:
            rm_conandir(pkg_folder)  # This will remove the shortened path too if exists
        except OSError as e:
            raise ConanException("%s\n\nFolder: %s\n"
                                 "Couldn't remove folder, might be busy or open\n"
                                 "Close any app using it, and retry" % (pkg_folder, str(e)))
        if is_dirty(pkg_folder):
            clean_dirty(pkg_folder)
        # FIXME: This fails at the moment, but should be fixed
        # with self.update_metadata() as metadata:
        #    metadata.clear_package(pref.id)

    def sources_remove(self):
        src_folder = os.path.join(self._base_folder, SRC_FOLDER)
        try:
            rm_conandir(src_folder)  # This will remove the shortened path too if exists
        except OSError as e:
            raise ConanException("%s\n\nFolder: %s\n"
                                 "Couldn't remove folder, might be busy or open\n"
                                 "Close any app using it, and retry" % (src_folder, str(e)))
        scm_folder = os.path.join(self._base_folder, SCM_SRC_FOLDER)
        try:
            rm_conandir(scm_folder)  # This will remove the shortened path too if exists
        except OSError as e:
            raise ConanException("%s\n\nFolder: %s\n"
                                 "Couldn't remove folder, might be busy or open\n"
                                 "Close any app using it, and retry" % (scm_folder, str(e)))

    def export_remove(self):
        export_folder = self.export()
        rmdir(export_folder)
        export_src_folder = os.path.join(self._base_folder, EXPORT_SRC_FOLDER)
        rm_conandir(export_src_folder)
        download_export = self.download_export()
        rmdir(download_export)
        scm_folder = os.path.join(self._base_folder, SCM_SRC_FOLDER)
        rm_conandir(scm_folder)

    def package_metadata(self):
        return os.path.join(self._base_folder, PACKAGE_METADATA)

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
