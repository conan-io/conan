import unittest
import platform
import os

from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANINFO
from conans.model.info import ConanInfo
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE_TXT
from conans.client.conf.detect import detected_os
from conans.util.files import load, mkdir, rmdir


class InvalidConfigurationTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": """
from conans import ConanFile
from conans.errors import ConanInvalidConfiguration

class MyPkg(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    
    def configure(self):
        if self.settings.compiler.version == "12":
            raise ConanInvalidConfiguration("user says that compiler.version=12 is invalid")

    """})
        settings = "-s os=Windows -s compiler='Visual Studio' -s compiler.version={ver}"
        self.settings_msvc15 = settings.format(ver="15")
        self.settings_msvc12 = settings.format(ver="12")

    def test_install_method(self):
        self.client.run("install . %s" % self.settings_msvc15)

        error = self.client.run("install . %s" % self.settings_msvc12, ignore_error=True)
        self.assertEqual(error, 5)  # TODO: hardcoded!!
        self.assertIn("Invalid configuration: user says that compiler.version=12 is invalid",
                      self.client.out)

    def test_create_method(self):
        self.client.run("create . name/ver@jgsogo/test %s" % self.settings_msvc15)

        error = self.client.run("create . name/ver@jgsogo/test %s" % self.settings_msvc12,
                                ignore_error=True)
        self.assertEqual(error, 5)  # TODO: hardcoded!!
        self.assertIn("name/ver@jgsogo/test: Invalid configuration: user says that "
                      "compiler.version=12 is invalid", self.client.out)

    def test_as_requirement(self):
        self.client.run("create . name/ver@jgsogo/test %s" % self.settings_msvc15)
        self.client.save({"other/conanfile.py": """
from conans import ConanFile
from conans.errors import ConanInvalidConfiguration

class MyPkg(ConanFile):
    requires = "name/ver@jgsogo/test"
    settings = "os", "compiler", "build_type", "arch"
    """})
        self.client.run("create other/ other/ver@jgsogo/test %s" % self.settings_msvc15)

        error = self.client.run("create other/ other/ver@jgsogo/test %s" % self.settings_msvc12,
                                ignore_error=True)
        self.assertEqual(error, 5)  # TODO: hardcoded!!
        self.assertIn("name/ver@jgsogo/test: Invalid configuration: user says that "
                      "compiler.version=12 is invalid", self.client.out)
