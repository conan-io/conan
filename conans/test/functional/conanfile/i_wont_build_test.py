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


class IWontBuildCompatiblePackagesTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.errors import ConanIWontBuild

        class Recipe(ConanFile):
            settings = "os", "compiler", "arch", "build_type"

            def configure(self):
                if self.settings.compiler.version == "15":
                    raise ConanIWontBuild("Invalid compiler version: 15")

            def package_id(self):
                if self.settings.compiler.version == "15":
                    for version in ("10", "12"):
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.compiler.version = version
                        self.compatible_packages.append(compatible_pkg)
        """)

    def test_compatible_package(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})

        # Create binaries for VS 12
        client.run("create . name/version@ -s compiler='Visual Studio' -s compiler.version=12")

        # It doesn't compile using VS 15
        error = client.run("install name/version@ -s compiler='Visual Studio'"
                           " -s compiler.version=15 --build=name", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("Invalid compiler version: 15", client.out)

        # ...but it can be consumed
        client.run("install name/version@ -s compiler='Visual Studio' -s compiler.version=15")
        self.assertIn("Using compatible package", client.out)
