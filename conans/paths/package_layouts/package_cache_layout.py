# coding=utf-8

import os
import platform

from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference
from conans.paths import CONANFILE, SYSTEM_REQS, EXPORT_FOLDER, EXPORT_SRC_FOLDER, SRC_FOLDER, \
    BUILD_FOLDER, PACKAGES_FOLDER, SYSTEM_REQS_FOLDER, SCM_FOLDER, PACKAGE_METADATA


def short_path(func):
    if platform.system() == "Windows":
        from conans.util.windows import path_shortener

        def wrap(self, *args, **kwargs):
            p = func(self,  *args, **kwargs)
            return path_shortener(p, self._short_paths)
        return wrap
    else:
        return func


class PackageCacheLayout(object):
    """ This is the package layout for Conan cache """

    def __init__(self, base_folder, ref, short_paths):
        assert isinstance(ref, ConanFileReference)
        self._ref = ref
        self._base_folder = os.path.normpath(base_folder)
        self._short_paths = short_paths

    def conan(self):
        """ Returns the base folder for this package reference """
        return self._base_folder

    def export(self):
        return os.path.join(self.conan(), EXPORT_FOLDER)

    @short_path
    def export_sources(self):
        return os.path.join(self.conan(), EXPORT_SRC_FOLDER)

    @short_path
    def source(self):
        return os.path.join(self.conan(), SRC_FOLDER)

    def conanfile(self):
        export = self.export()
        return os.path.join(export, CONANFILE)

    def builds(self):
        return os.path.join(self.conan(), BUILD_FOLDER)

    @short_path
    def build(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        return os.path.join(self.conan(), BUILD_FOLDER, pref.id)

    def system_reqs(self):
        return os.path.join(self.conan(), SYSTEM_REQS_FOLDER, SYSTEM_REQS)

    def system_reqs_package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        return os.path.join(self.conan(), SYSTEM_REQS_FOLDER, pref.id, SYSTEM_REQS)

    def packages(self):
        return os.path.join(self.conan(), PACKAGES_FOLDER)

    @short_path
    def package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        return os.path.join(self.conan(), PACKAGES_FOLDER, pref.id)

    def scm_folder(self):
        return os.path.join(self.conan(), SCM_FOLDER)

    def package_metadata(self):
        return os.path.join(self.conan(), PACKAGE_METADATA)
