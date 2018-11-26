# coding=utf-8

import os
import re
import configparser
import ntpath
import posixpath

from conans.paths import CONANFILE
from conans.util.files import load
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference

CONAN_PACKAGE_LAYOUT_FILE = '.conan_package_layout'


class PackageEditableLayout(object):

    def __init__(self, linked_package_file, conan_ref):
        assert isinstance(conan_ref, ConanFileReference)
        self._conan_ref = conan_ref
        self._base_folder = os.path.normpath(load(linked_package_file))

    def conan(self):
        """ Returns the base folder for this package reference """
        return self._base_folder

    def conanfile(self):
        """ Path to the conanfile. We can agree that an editable package needs to be a Conan package """
        return os.path.join(self.conan(), CONANFILE)

    def installed_as_editable(self):
        return True

    def editable_package_layout_file(self):
        return os.path.join(self.conan(), CONAN_PACKAGE_LAYOUT_FILE)

    def package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        assert package_reference.conan == self._conan_ref
        raise RuntimeError("Cannot retrieve this path for an editable package")
        return self.conan()
        return os.path.join(self.conan(), "package_reference")

    def package_metadata(self):
        # FIXME: I know that downstream there is an except for this
        raise IOError("Package metadata is not available for editable packages")


def parse_package_layout_content(content, base_path=None):
    """ Returns a dictionary containing information about paths for a CppInfo object: includes,
    libraries, resources, binaries,... """
    ret = {k: [] for k in ['includedirs', 'libdirs', 'resdirs', 'bindirs']}

    def make_abs(value):
        value = re.sub(r'\\\\+', r'\\', value)
        value = value.replace('\\', '/')
        isabs = ntpath.isabs(value) or posixpath.isabs(value)
        if base_path and not isabs:
            value = os.path.abspath(os.path.join(base_path, value))
        value = os.path.normpath(value)
        return value

    parser = configparser.ConfigParser(allow_no_value=True, delimiters=('#', ))
    parser.optionxform = str
    parser.read_string(content)
    for section in ret.keys():
        if section in parser:
            ret[section] = [make_abs(value) for value in parser[section]]
    return ret
