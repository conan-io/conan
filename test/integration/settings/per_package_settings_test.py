import json
import textwrap
import unittest

from conan.test.utils.tools import TestClient, GenConanfile


class PerPackageSettingTest(unittest.TestCase):

    def test_per_package_setting(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Windows")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("create . --name=consumer --version=0.1 --user=user --channel=testing -s os=Linux -s pkg*:os=Windows")
        self.assertIn("consumer/0.1@user/testing: Created package", client.out)

    def test_per_package_setting_build_type(self):
        """ comes from https://github.com/conan-io/conan/pull/9842
        In Conan 1.X there was a weird behavior if you used different patterns,
        only first matching one win. This was broken:
          -s pkg*:os=Windows -s *model:build_type=Debug
        keeps the build_type=Release, because pkg* matches, assign os=Windows and stops
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg-model"
                version = "0.1"
                settings = "os", "build_type"
                def build(self):
                    self.output.info("BUILDTYPE {}:{}!!!!".format(self.settings.os,
                                                                  self.settings.build_type))
            """)
        client.save({"conanfile.py": conanfile})
        # Different pattern, no issue, works now
        client.run("create . -s *:os=Windows -s *-model*:build_type=Debug -s build_type=Release")
        assert "pkg-model/0.1: BUILDTYPE Windows:Debug!!!!" in client.out

        client.save({"conanfile.py": GenConanfile("consumer", "0.1").with_require("pkg-model/0.1")})
        client.run('create . -s *:os=Linux -s *-model*:os=Windows '
                   '-s "*-model*:build_type=Debug" -s build_type=Release --build=*')
        assert "pkg-model/0.1: BUILDTYPE Windows:Debug!!!!" in client.out
        self.assertIn("consumer/0.1: Created package", client.out)

    def test_per_package_setting_no_userchannel(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 -s os=Windows")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
        client.run("create . --name=consumer --version=0.1 -s os=Linux -s pkg*:os=Windows")
        self.assertIn("consumer/0.1: Created package", client.out)

    def test_per_package_subsetting(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler"
            """)
        client.save({"conanfile.py": conanfile})
        settings = "-s os=Linux -s compiler=gcc -s compiler.version=5"
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing %s  -s compiler.libcxx=libstdc++11" % settings)
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("create . --name=consumer --version=0.1 --user=user --channel=testing %s -s compiler.libcxx=libstdc++ "
                   "-s pkg*:compiler.libcxx=libstdc++11" % settings)
        self.assertIn("consumer/0.1@user/testing: Created package", client.out)

    def test_per_package_setting_all_packages_without_user_channel(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                def configure(self):
                    self.output.info(f"I am a {self.settings.os} pkg!!!")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg1 --version=0.1 -s os=Windows")
        client.run("create . --name=pkg2 --version=0.1 --user=user -s os=Linux")
        client.run("create . --name=pkg3 --version=0.1 --user=user --channel=channel -s os=Linux")
        client.save({"conanfile.py": GenConanfile().with_requires("pkg1/0.1", "pkg2/0.1@user",
                                                                  "pkg3/0.1@user/channel")})
        client.run("install . -s os=Linux -s *@:os=Windows")
        assert "pkg1/0.1: I am a Windows pkg!!!" in client.out
        assert "pkg2/0.1@user: I am a Linux pkg!!!" in client.out
        assert "pkg3/0.1@user/channel: I am a Linux pkg!!!" in client.out


def test_per_package_settings_target():
    c = TestClient()
    gcc = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "gcc"
            version = "0.1"
            settings = "arch"

            def configure(self):
                self.settings_target.rm_safe("os")
                self.settings_target.rm_safe("compiler")
                self.settings_target.rm_safe("build_type")

            def package_id(self):
                self.info.settings_target = self.settings_target
        """)
    c.save({"conanfile.py": gcc})
    c.run("create . -s:b arch=x86_64 -s:h arch=armv7 --build-require")
    pkg_id = c.created_package_id("gcc/0.1")

    c.run("install --tool-requires=gcc/0.1 -s:b arch=x86_64 -s arch=armv8 -s:h gcc*:arch=armv7"
          " --format=json")
    # it will not fail due to armv8, but use the binary for armv7
    c.assert_listed_binary({"gcc/0.1": (pkg_id, "Cache")}, build=True)

    graph = json.loads(c.stdout)
    assert graph["graph"]["nodes"]["1"]["info"]["settings_target"] == {"arch": "armv7"}


def test_per_package_settings_build():
    c = TestClient()
    cmake = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "cmake"
            version = "0.1"
            settings = "build_type"

            def build(self):
                self.output.info(f"Building myself with {self.settings.build_type}!!")
        """)
    c.save({"conanfile.py": cmake})
    c.run("export .")

    c.run("install --tool-requires=cmake/0.1 -s:b build_type=Release -s:b cmake*:build_type=Debug "
          "--build=missing")
    assert "cmake/0.1: Building myself with Debug!!" in c.out


def test_package_settings_mixed_patterns():
    # https://github.com/conan-io/conan/issues/16606
    c = TestClient()
    profile = textwrap.dedent("""
        [settings]
        arch=x86_64
        *@test/*:build_type=Release

        os=Linux
        compiler=gcc
        &:compiler.version=12
        compiler.libcxx = libstdc++
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "mypkg"
            version = "0.1"
            settings = "os", "arch", "compiler", "build_type"
            def build(self):
                self.output.info(f"BUILD_TYPE={self.settings.build_type}!")
                self.output.info(f"COMPILER_VERSION={self.settings.compiler.version}!")
                self.output.info(f"COMPILER_LIBCXX={self.settings.compiler.libcxx}!")
            """)
    c.save({"profile": profile,
            "conanfile.py": conanfile})
    c.run("create . -pr=profile --user=test --channel=test")
    assert "mypkg/0.1@test/test: BUILD_TYPE=Release!" in c.out
    assert "mypkg/0.1@test/test: COMPILER_VERSION=12!" in c.out
    assert "mypkg/0.1@test/test: COMPILER_LIBCXX=libstdc++!" in c.out
