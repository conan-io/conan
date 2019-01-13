# coding=utf-8

import os

from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference
from conans.paths import CONANFILE, CONAN_PACKAGE_LAYOUT_FILE
from conans.model.editable_cpp_info import EditableCppInfo


class PackageEditableLayout(object):

    def __init__(self, base_folder, layout_file, ref):
        assert isinstance(ref, ConanFileReference)
        self._ref = ref
        self._base_folder = base_folder
        self._layout_file = layout_file

    def conan(self):
        """ Returns the base folder for this package reference """
        return self._base_folder

    def conanfile(self):
        """ Path to the conanfile. We can agree that an editable package
            needs to be a Conan package
        """
        return os.path.join(self.conan(), CONANFILE)

    def layout_file(self):
        return self._layout_file

    def editable_cpp_info(self):
        local_file = self._layout_file or CONAN_PACKAGE_LAYOUT_FILE
        local_file = os.path.join(self.conan(), local_file)
        if os.path.exists(local_file):
            return EditableCppInfo.load(local_file, require_namespace=False)

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


