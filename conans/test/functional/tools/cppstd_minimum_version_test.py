import unittest
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

    def test_cppstd_from_settings(self):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=17")
        self.client.save({"myprofile":  profile})
        self.client.run("create . user/channel -pr myprofile")
        self.assertIn("valid standard", self.client.out)

    def test_invalid_cppstd_from_settings(self):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "compiler.cppstd=11")
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile", assert_error=True)
        self.assertIn("Invalid configuration: Current cppstd (11) is lower than required c++ "
                      "standard (17).", self.client.out)

    def test_cppstd_from_arguments(self):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "")
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile -s compiler.cppstd=17")
        self.assertIn("valid standard", self.client.out)

    def test_invalid_cppstd_from_arguments(self):
        profile = CppStdMinimumVersionTests.PROFILE.replace("{}", "")
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel --pr myprofile -s compiler.cppstd=11",
                        assert_error=True)
        self.assertIn("Invalid configuration: Current cppstd (11) is lower than required c++ "
                      "standard (17).", self.client.out)

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
