# coding=utf-8

import os
import platform

from conans.constants import CONANFILE, SYSTEM_REQS
from conans.errors import ConanException
from conans.model.ref import PackageReference
from conans.client.package_layouts.package_base_layout import PackageBaseLayout

EXPORT_FOLDER = "export"
EXPORT_SRC_FOLDER = "export_source"
SRC_FOLDER = "source"
BUILD_FOLDER = "build"
PACKAGES_FOLDER = "package"
SYSTEM_REQS_FOLDER = "system_reqs"

SCM_FOLDER = "scm_folder.txt"


if platform.system() == "Windows":
    from conans.util.windows import path_shortener
else:
    def path_shortener(x, _):
        return x


def is_case_insensitive_os():
    system = platform.system()
    return system != "Linux" and system != "FreeBSD" and system != "SunOS"


if is_case_insensitive_os():
    def check_ref_case(conan_reference, conan_folder, store_folder):
        if not os.path.exists(conan_folder):  # If it doesn't exist, not a problem
            return
        # If exists, lets check path
        tmp = store_folder
        for part in conan_reference:
            items = os.listdir(tmp)
            if part not in items:
                offending = ""
                for item in items:
                    if item.lower() == part.lower():
                        offending = item
                        break
                raise ConanException("Requested '%s' but found case incompatible '%s'\n"
                                     "Case insensitive filesystem can't manage this"
                                     % (str(conan_reference), offending))
            tmp = os.path.normpath(tmp + os.sep + part)
else:
    def check_ref_case(conan_reference, conan_folder, store_folder):  # @UnusedVariable
        pass


class PackageCacheLayout(PackageBaseLayout):
    """ This is the package layout for Conan cache """

    def export(self):
        return os.path.join(self.conan(), EXPORT_FOLDER)

    def export_sources(self):
        p = os.path.join(self.conan(), EXPORT_SRC_FOLDER)
        return path_shortener(p, self._short_paths)

    def source(self):
        p = os.path.join(self.conan(), SRC_FOLDER)
        return path_shortener(p, self._short_paths)

    def conanfile(self):
        export = self.export()
        check_ref_case(self._conan_ref, export, self._base_folder)
        return os.path.join(export, CONANFILE)

    def builds(self):
        return os.path.join(self.conan(), BUILD_FOLDER)

    def build(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        assert package_reference.conan == self._conan_ref
        p = os.path.join(self.conan(), BUILD_FOLDER, package_reference.package_id)
        return path_shortener(p, self._short_paths)

    def system_reqs(self):
        return os.path.join(self.conan(), SYSTEM_REQS_FOLDER, SYSTEM_REQS)

    def system_reqs_package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        assert package_reference.conan == self._conan_ref
        return os.path.join(self.conan(), SYSTEM_REQS_FOLDER,
                            package_reference.package_id, SYSTEM_REQS)

    def packages(self):
        return os.path.join(self.conan(), PACKAGES_FOLDER)

    def package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        assert package_reference.conan == self._conan_ref
        p = os.path.join(self.conan(), PACKAGES_FOLDER, package_reference.package_id)
        return path_shortener(p, self._short_paths)

    def scm_folder(self):
        return os.path.join(self.conan(), SCM_FOLDER)
