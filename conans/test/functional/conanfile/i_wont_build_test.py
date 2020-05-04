import textwrap
import unittest

from conans.client.command import ERROR_INVALID_CONFIGURATION
from conans.test.utils.tools import TestClient


class IWontBuildTestCase(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": textwrap.dedent("""
            from conans import ConanFile
            from conans.errors import ConanIWontBuild

            class MyPkg(ConanFile):
                settings = "os", "compiler", "build_type", "arch"

                def configure(self):
                    if self.settings.compiler.version == "10":
                        raise ConanIWontBuild("won't build with compiler.version=10")

                """)})
        settings = "-s os=Windows -s compiler='Visual Studio' -s compiler.version={ver}"
        self.settings_msvc15 = settings.format(ver="15")
        self.settings_msvc10 = settings.format(ver="10")

    def test_install_method(self):
        self.client.run("install . %s" % self.settings_msvc15, assert_error=False)
        self.client.run("install . %s" % self.settings_msvc10, assert_error=False)

    def test_info_method(self):
        self.client.run("info . %s" % self.settings_msvc15, assert_error=False)
        self.client.run("info . %s" % self.settings_msvc10, assert_error=False)

    def test_create_method(self):
        self.client.run("create . name/ver@jgsogo/test %s" % self.settings_msvc15)

        error = self.client.run("create . name/ver@jgsogo/test %s" % self.settings_msvc10,
                                assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("ERROR: name/ver@jgsogo/test: Invalid configuration: won't"
                      " build with compiler.version=10", self.client.out)

    def test_as_requirement(self):
        self.client.run("create . name/ver@jgsogo/test %s" % self.settings_msvc15)
        self.client.save({"other/conanfile.py": textwrap.dedent("""
            from conans import ConanFile
            from conans.errors import ConanIWontBuild

            class MyPkg(ConanFile):
                requires = "name/ver@jgsogo/test"
                settings = "os", "compiler", "build_type", "arch"
                """)})
        self.client.run("create other/ other/ver@jgsogo/test %s" % self.settings_msvc15)

        error = self.client.run("create other/ other/ver@ %s --build missing" % self.settings_msvc10,
                                assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("ERROR: name/ver@jgsogo/test: Invalid configuration: won't"
                      " build with compiler.version=10", self.client.out)
