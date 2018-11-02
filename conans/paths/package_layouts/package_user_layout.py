# coding=utf-8

import os

from conans.util.files import load
from conans.model.ref import ConanFileReference


class PackageUserLayout(object):

    def __init__(self, linked_package_file, conan_ref):
        assert isinstance(conan_ref, ConanFileReference)
        self._conan_ref = conan_ref
        self._base_folder = os.path.normpath(load(linked_package_file))

    def conan(self):
        """ Returns the base folder for this package reference """
        return self._base_folder
