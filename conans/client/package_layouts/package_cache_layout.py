# coding=utf-8

import os
import platform

from conans.constants import CONANFILE, SYSTEM_REQS
from conans.model.ref import PackageReference
from conans.client.package_layouts.package_base_layout import PackageBaseLayout

EXPORT_FOLDER = "export"
EXPORT_SRC_FOLDER = "export_source"
SRC_FOLDER = "source"
BUILD_FOLDER = "build"
PACKAGES_FOLDER = "package"
SYSTEM_REQS_FOLDER = "system_reqs"

SCM_FOLDER = "scm_folder.txt"


def short_path(func):
    if platform.system() == "Windows":
        from conans.util.windows import path_shortener

        def wrap(self, *args, **kwargs):
            p = func(self,  *args, **kwargs)
            return path_shortener(p, self._short_paths)
        return wrap
    else:
        return func


class PackageCacheLayout(PackageBaseLayout):
    """ This is the package layout for Conan cache """

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
    def build(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        assert package_reference.conan == self._conan_ref
        return os.path.join(self.conan(), BUILD_FOLDER, package_reference.package_id)

    def system_reqs(self):
        return os.path.join(self.conan(), SYSTEM_REQS_FOLDER, SYSTEM_REQS)

    def system_reqs_package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        assert package_reference.conan == self._conan_ref
        return os.path.join(self.conan(), SYSTEM_REQS_FOLDER,
                            package_reference.package_id, SYSTEM_REQS)

    def packages(self):
        return os.path.join(self.conan(), PACKAGES_FOLDER)

    @short_path
    def package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        assert package_reference.conan == self._conan_ref
        return os.path.join(self.conan(), PACKAGES_FOLDER, package_reference.package_id)

    def scm_folder(self):
        return os.path.join(self.conan(), SCM_FOLDER)
