# coding=utf-8

import os

from conans.errors import ConanException
from conans.model.editable_layout import EditableLayout
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference
from conans.paths import CONANFILE


class PackageEditableLayout(object):

    def __init__(self, base_folder, layout_file, ref):
        assert isinstance(ref, ConanFileReference)
        self._ref = ref
        self._base_folder = base_folder
        self._layout_file = layout_file

    @property
    def ref(self):
        return self._ref

    def conan(self):
        """ Returns the base folder for this package reference """
        return self._base_folder

    def conanfile(self):
        """ Path to the conanfile. We can agree that an editable package
            needs to be a Conan package
        """
        return os.path.join(self._base_folder, CONANFILE)

    def editable_cpp_info(self):
        if self._layout_file:
            if os.path.isfile(self._layout_file):
                return EditableLayout(self._layout_file)
            else:
                raise ConanException("Layout file not found: %s" % self._layout_file)

    def export(self):
        raise ConanException("Operation not allowed on a package installed as editable")

    def export_sources(self):
        raise ConanException("Operation not allowed on a package installed as editable")

    def source(self):
        raise ConanException("Operation not allowed on a package installed as editable")

    def load_metadata(self):
        raise ConanException("Operation not allowed on a package installed as editable")

    def package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        raise ConanException("Operation not allowed on a package installed as editable")

    def package_metadata(self):
        raise ConanException("Package metadata is not available for editable packages")

    def get_path(self, package_id=None, path=None):
        raise ConanException("Operation not allowed on a package installed as editable")
