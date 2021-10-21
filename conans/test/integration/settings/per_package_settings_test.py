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

    def test_per_package_setting_build_type(self):
        # FIXME this is weird behavior if you use different patterns, only first matching one win:
        # FIXME -s pkg*:os=Windows -s *model:build_type=Debug
        # FIXME keeps the build_type=Release, because pkg* matches, assign os=Windows and stops
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os", "build_type"
                def build(self):
                    self.output.info("BUILDTYPE {}!!!!".format(self.settings.build_type))
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg-model/0.1@user/testing -s os=Windows -s *-model*:build_type=Debug "
                   "-s build_type=Release")
        assert "pkg-model/0.1@user/testing: BUILDTYPE Debug!!!!" in client.out

        client.save({"conanfile.py": GenConanfile().with_require("pkg-model/0.1@user/testing")})
        client.run('create . consumer/0.1@user/testing -s os=Linux -s *-model*:os=Windows '
                   '-s "*-model*:build_type=Debug" -s build_type=Release --build')
        assert "pkg-model/0.1@user/testing: BUILDTYPE Debug!!!!" in client.out
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
