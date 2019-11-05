import unittest
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
                cppstd_minimum_required(self, "17")
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
        self.assertIn("Invalid configuration: Current compiler does not not support the required "
                      "c++ standard (17).", self.client.out)
