import unittest
import mock
from parameterized import parameterized
from textwrap import dedent

from conans.test.utils.tools import TestClient


class CppStdMinimumVersionTests(unittest.TestCase):

    CONANFILE = dedent("""
        import os
        from conans import ConanFile
        from conans.tools import cppstd_minimum_required

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"

            def configure(self):
                cppstd_minimum_required(self, "17", False)
                self.output.info("valid standard")
        """)

    PROFILE = dedent("""
        [settings]
        compiler=gcc
        compiler.version=9
        compiler.libcxx=libstdc++
        {}
        """)

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE})

    @parameterized.expand(["17", "gnu17"])
    def test_cppstd_from_settings(self, cppstd):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile":  profile})
        self.client.run("create . user/channel -pr myprofile")
        self.assertIn("valid standard", self.client.out)

    @parameterized.expand(["11", "gnu11"])
    def test_invalid_cppstd_from_settings(self, cppstd):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile", assert_error=True)
        self.assertIn("Invalid configuration: Current cppstd (%s) is lower than required c++ "
                      "standard (17)." % cppstd, self.client.out)

    @parameterized.expand(["17", "gnu17"])
    def test_cppstd_from_arguments(self, cppstd):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "")
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile -s compiler.cppstd=%s" % cppstd)
        self.assertIn("valid standard", self.client.out)

    @parameterized.expand(["11", "gnu11"])
    def test_invalid_cppstd_from_arguments(self, cppstd):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "")
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel --pr myprofile -s compiler.cppstd=%s" % cppstd,
                        assert_error=True)
        self.assertIn("Invalid configuration: Current cppstd (%s) is lower than required c++ "
                      "standard (17)." % cppstd, self.client.out)

    def test_cppstd_from_compiler(self):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "")
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile")
        self.assertIn("valid standard", self.client.out)

    def test_invalid_cppstd_from_compiler(self):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "").replace("9", "4.9")
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile", assert_error=True)
        self.assertIn("Invalid configuration: Current compiler does not support the required "
                      "c++ standard (17).", self.client.out)

    @parameterized.expand([["gnu17", "Linux"], ["gnu17", "Windows"]])
    def test_valid_gnu_extensions_from_settings(self, cppstd, os):
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE.replace("False",
                                                                                      "True")})
        with mock.patch("platform.system", mock.MagicMock(return_value=os)):
            profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
            self.client.save({"myprofile": profile})
            self.client.run("create . user/channel -pr myprofile")
            self.assertIn("valid standard", self.client.out)

    @parameterized.expand([
        ["17", "Linux", "Invalid configuration: Current cppstd (17) does not have GNU extensions, "
                        "which is required on Linux platform.", True],
        ["17", "Windows", "valid standard", False]])
    def test_invalid_gnu_extensions_from_settings(self, cppstd, system, expected, error):
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE.replace("False",
                                                                                      "True")})
        with mock.patch("platform.system", mock.MagicMock(return_value=system)):
            profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
            self.client.save({"myprofile": profile})
            self.client.run("create . user/channel -pr myprofile", assert_error=error)
            self.assertIn(expected, self.client.out)

    @parameterized.expand([["gnu17", "Linux"], ["gnu17", "Windows"]])
    def test_gnu_extensions_from_arguments(self, cppstd, os):
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE.replace("False",
                                                                                      "True")})
        self.client.save({"myprofile": CppStdMinimumVersionTests.PROFILE.replace("{}", "")})
        with mock.patch("platform.system", mock.MagicMock(return_value=os)):
            self.client.run("create . user/channel -pr myprofile -s compiler.cppstd=%s" % cppstd)
            self.assertIn("valid standard", self.client.out)

    @parameterized.expand([["17", "Linux", "Invalid configuration: Current cppstd (17) does not "
                           "have GNU extensions, which is required on Linux platform.", True],
                          ["17", "Windows", "valid standard", False]])
    def test_invalid_gnu_extensions_from_arguments(self, cppstd, os, expected, error):
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE.replace("False",
                                                                                      "True")})
        self.client.save({"myprofile": CppStdMinimumVersionTests.PROFILE.replace("{}", "")})
        with mock.patch("platform.system", mock.MagicMock(return_value=os)):
            self.client.run("create . user/channel --pr myprofile -s compiler.cppstd=%s" % cppstd,
                            assert_error=error)
            self.assertIn(expected, self.client.out)

    def test_gnu_extensions_from_compiler(self):
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE.replace("False",
                                                                                      "True")})
        self.client.save({"myprofile": CppStdMinimumVersionTests.PROFILE.replace("{}", "")})
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")):
            self.client.run("create . user/channel -pr myprofile")
            self.assertIn("valid standard", self.client.out)

    @parameterized.expand([["Linux", "gnu17"],
                           ["Windows", "17"]])
    def test_invalid_gnu_extensions_from_compiler(self, os, expected):
        self.client.save({"conanfile.py": CppStdMinimumVersionTests.CONANFILE.replace("False",
                                                                                      "True")})
        self.client.save({"myprofile": CppStdMinimumVersionTests.PROFILE.replace("{}", "")
                                                                        .replace("9", "4.9")})
        with mock.patch("platform.system", mock.MagicMock(return_value=os)):
            self.client.run("create . user/channel -pr myprofile", assert_error=True)
            self.assertIn("Invalid configuration: Current compiler does not support the "
                          "required c++ standard (%s)." % expected, self.client.out)
