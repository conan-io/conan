import unittest
from parameterized import parameterized
from textwrap import dedent

from conans.test.utils.tools import TestClient


class CppStdCheckTests(unittest.TestCase):

    CONANFILE = dedent("""
        import os
        from conans import ConanFile
        from conans.tools import check_cppstd

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"

            def configure(self):
                check_cppstd(self, minimum="11", maximum="14")
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
        self.client.save({"conanfile.py": CppStdCheckTests.CONANFILE})

    @parameterized.expand(["11", "gnu11"])
    def test_cppstd_from_settings(self, cppstd):
        profile = CppStdCheckTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile":  profile})
        self.client.run("create . user/channel -pr myprofile")
        self.assertIn("valid standard", self.client.out)

    @parameterized.expand(["17", "gnu17"])
    def test_invalid_cppstd_from_settings(self, cppstd):
        profile = CppStdCheckTests.PROFILE.replace("{}", "compiler.cppstd=%s" % cppstd)
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile", assert_error=True)
        self.assertIn("Invalid configuration: Current cppstd (%s) is higher than the maximum required C++ "
                      "standard (14)" % cppstd, self.client.out)
