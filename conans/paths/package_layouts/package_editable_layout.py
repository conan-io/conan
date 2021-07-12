# coding=utf-8

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference


class PackageEditableLayout(object):

    def __init__(self, base_folder, ref, conanfile_path):
        assert isinstance(ref, ConanFileReference)
        self._ref = ref
        self._base_folder = base_folder
        self._conanfile_path = conanfile_path

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
        return self._conanfile_path

    def export(self):
        raise ConanException("Operation not allowed on a package installed as editable")

    def conanfile_write_lock(self, output):
        raise ConanException("Operation not allowed on a package installed as editable")

    def export_sources(self):
        raise ConanException("Operation not allowed on a package installed as editable")

    def source(self):
        raise ConanException("Operation not allowed on a package installed as editable")

    def package(self, pref):
        assert isinstance(pref, PackageReference)
        assert pref.ref == self._ref
        raise ConanException("Operation not allowed on a package installed as editable")

    def get_path(self, package_id=None, path=None):
        raise ConanException("Operation not allowed on a package installed as editable")

    def package_ids(self):
        raise ConanException("Package in editable mode cannot list binaries")
