# coding=utf-8

import os

from conans.errors import ConanException
from conans.model.ref import PackageReference
from conans.paths import CONANFILE


class PackageLocalLayout(object):

    def __init__(self, base_folder, ref=None):
        self._base_folder = base_folder
        self._ref = ref

    @property
    def ref(self):
        return self._ref

    def base_folder(self):
        """ Returns the base folder for this package reference """
        return self._base_folder

    def conanfile(self):
        """ Path to the conanfile. We can agree that an editable package
            needs to be a Conan package
        """
        return os.path.join(self._base_folder, CONANFILE)

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
        # assert pref.ref == self._ref
        raise ConanException("Operation not allowed on a package installed as editable")

    def package_metadata(self):
        raise ConanException("Package metadata is not available for editable packages")

    def get_path(self, package_id=None, path=None):
        raise ConanException("Operation not allowed on a package installed as editable")
