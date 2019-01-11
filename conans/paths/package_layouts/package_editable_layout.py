# coding=utf-8

import os

from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference
from conans.paths import CONANFILE, CONAN_PACKAGE_LAYOUT_FILE


class PackageEditableLayout(object):

    def __init__(self, base_folder, ref):
        assert isinstance(ref, ConanFileReference)
        self.ref = ref
        self._base_folder = base_folder

    def conan(self):
        """ Returns the base folder for this package reference """
        return self._base_folder

    def conanfile(self):
        """ Path to the conanfile. We can agree that an editable package
            needs to be a Conan package
        """
        return os.path.join(self.conan(), CONANFILE)

    def editable_package_layout_file(self):
        return os.path.join(self.conan(), CONAN_PACKAGE_LAYOUT_FILE)

    def export(self):
        raise RuntimeError("Operation not allowed on a package installed as editable")

    def export_sources(self):
        raise RuntimeError("Operation not allowed on a package installed as editable")

    def source(self):
        raise RuntimeError("Operation not allowed on a package installed as editable")

    def package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        raise RuntimeError("Operation not allowed on a package installed as editable")

    def package_metadata(self):
        # FIXME: I know that downstream there is an except for IOError
        raise IOError("Package metadata is not available for editable packages")


