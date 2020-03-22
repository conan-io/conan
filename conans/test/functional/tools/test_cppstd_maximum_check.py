import unittest
from parameterized import parameterized
from textwrap import dedent

from conans.test.utils.tools import TestClient


class CppStdMaximumCheckTests(unittest.TestCase):

    CONANFILE = dedent("""
        import os
        from conans import ConanFile
        from conans.tools import check_max_cppstd, valid_max_cppstd

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"

            def configure(self):
                check_max_cppstd(self, "11", False)
                self.output.info("valid standard")
                assert valid_max_cppstd(self, "11", False)
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
        self.client.save({"conanfile.py": CppStdMaximumCheckTests.CONANFILE})

    @parameterized.expand(["11", "gnu11"])
    def test_cppstd_from_settings(self, cppstd):
        profile = CppStdMaximumCheckTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile":  profile})
        self.client.run("create . user/channel -pr myprofile")
        self.assertIn("valid standard", self.client.out)

    @parameterized.expand(["17", "gnu17"])
    def test_invalid_cppstd_from_settings(self, cppstd):
        profile = CppStdMaximumCheckTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile", assert_error=True)
        self.assertIn("Invalid configuration: Current cppstd (%s) is higher than the required C++ "
                      "standard (11)." % cppstd, self.client.out)
