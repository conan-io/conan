import unittest
from parameterized import parameterized
from textwrap import dedent

from conans.test.utils.tools import TestClient


class CompilerCheckTests(unittest.TestCase):

    CONANFILE = dedent("""
        import os
        from conans import ConanFile
        from conans.tools import check_compiler

        class Fake(ConanFile):
            name = "fake"
            version = "0.1"
            settings = "compiler"

            def configure(self):
                check_compiler(self, required={"gcc": "7"})
                self.output.info("valid compiler")
        """)

    PROFILE = dedent("""
        [settings]
        compiler=gcc
        compiler.version={}
        compiler.libcxx=libstdc++
        """)

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": CompilerCheckTests.CONANFILE})

    @parameterized.expand(["7", "7.1", "8"])
    def test_version_from_settings(self, version):
        profile = CompilerCheckTests.PROFILE.replace("{}", "{}".format(version))
        self.client.save({"myprofile":  profile})
        self.client.run("create . user/channel -pr myprofile")
        self.assertIn("valid compiler", self.client.out)

    @parameterized.expand(["5", "5.4", "6"])
    def test_invalid_version_from_settings(self, version):
        profile = CompilerCheckTests.PROFILE.replace("{}", "{}".format(version))
        self.client.save({"myprofile": profile})
        self.client.run("create . user/channel -pr myprofile", assert_error=True)
        self.assertIn("Invalid configuration: At least gcc 7 is required", self.client.out)
