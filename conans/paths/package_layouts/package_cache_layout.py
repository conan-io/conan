# coding=utf-8

import os
import platform
from contextlib import contextmanager

from conans.errors import NotFoundException
from conans.errors import RecipeNotFoundException, PackageNotFoundException
from conans.model.manifest import FileTreeManifest
from conans.model.manifest import discarded_file
from conans.model.package_metadata import PackageMetadata
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference
from conans.paths import CONANFILE, SYSTEM_REQS, EXPORT_FOLDER, EXPORT_SRC_FOLDER, SRC_FOLDER, \
    BUILD_FOLDER, PACKAGES_FOLDER, SYSTEM_REQS_FOLDER, SCM_FOLDER, PACKAGE_METADATA
from conans.util.files import load, save, rmdir
from conans.util.locks import Lock, NoLock, ReadLock, SimpleLock, WriteLock


def short_path(func):
    if platform.system() == "Windows":
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

    def conan(self):
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

    def packages(self):
        return os.path.join(self._base_folder, PACKAGES_FOLDER)

    @short_path
    def package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        return os.path.join(self._base_folder, PACKAGES_FOLDER, pref.id)

    def scm_folder(self):
        return os.path.join(self._base_folder, SCM_FOLDER)

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

    def conan_packages(self):
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

    @contextmanager
    def update_metadata(self):
        try:
            metadata = self.load_metadata()
        except RecipeNotFoundException:
            metadata = PackageMetadata()
        yield metadata
        save(self.package_metadata(), metadata.dumps())

    # Revisions
    def package_summary_hash(self, pref):
        package_folder = self.package(pref)
        try:
            read_manifest = FileTreeManifest.load(package_folder)
        except IOError:
            raise PackageNotFoundException(pref)
        return read_manifest.summary_hash

    # Locks
    def conanfile_read_lock(self, output):
        if self._no_lock:
            return NoLock()
        return ReadLock(self.conan(), self._ref, output)

    def conanfile_write_lock(self, output):
        if self._no_lock:
            return NoLock()
        return WriteLock(self.conan(), self._ref, output)

    def conanfile_lock_files(self, output):
        if self._no_lock:
            return ()
        return WriteLock(self.conan(), self._ref, output).files

    def package_lock(self, pref):
        if self._no_lock:
            return NoLock()
        return SimpleLock(os.path.join(self.conan(), "locks", pref.id))

    def remove_package_locks(self):
        conan_folder = self.conan()
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
            return sorted([path for path in os.listdir(abs_path) if not discarded_file(path)])
        else:
            return load(abs_path)
