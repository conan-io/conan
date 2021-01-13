import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class PerPackageSettingTest(unittest.TestCase):

    def test_per_package_setting(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/testing -s os=Windows")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("create . consumer/0.1@user/testing -s os=Linux -s pkg*:os=Windows")
        self.assertIn("consumer/0.1@user/testing: Created package", client.out)

    def test_per_package_setting_no_userchannel(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@ -s os=Windows")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
        client.run("create . consumer/0.1@ -s os=Linux -s pkg*:os=Windows")
        self.assertIn("consumer/0.1: Created package", client.out)

    def test_per_package_subsetting(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler"
            """)
        client.save({"conanfile.py": conanfile})
        settings = "-s os=Linux -s compiler=gcc -s compiler.version=5"
        client.run("create . pkg/0.1@user/testing %s  -s compiler.libcxx=libstdc++11" % settings)
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("create . consumer/0.1@user/testing %s -s compiler.libcxx=libstdc++ "
                   "-s pkg:compiler.libcxx=libstdc++11" % settings)
        self.assertIn("consumer/0.1@user/testing: Created package", client.out)
