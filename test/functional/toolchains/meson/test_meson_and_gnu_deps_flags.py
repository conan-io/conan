import os
import platform
import textwrap

import pytest

from test.functional.toolchains.meson._base import TestMesonBase
from conan.test.utils.tools import TestClient


class TestMesonToolchainAndGnuFlags(TestMesonBase):

    @pytest.mark.tool("meson")
    @pytest.mark.tool("pkg_config")
    def test_mesondeps_flags_are_being_appended_and_not_replacing_toolchain_ones(self):
        """
        Test PkgConfigDeps and MesonToolchain are keeping all the flags/definitions defined
        from both generators and nothing is being messed up.
        """
        client = TestClient(path_with_spaces=False)
        if platform.system() == "Windows":
            deps_flags = '"/GA", "/analyze:quiet"'
            flags = '"/Wall", "/W4"'
        else:
            deps_flags = '"-Wpedantic", "-Werror"'
            flags = '"-Wall", "-finline-functions"'
        # Dependency - hello/0.1
        conanfile_py = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"

            def package_info(self):
                self.cpp_info.cxxflags = [{}]
                self.cpp_info.defines = ['DEF1=one_string', 'DEF2=other_string']
        """.format(deps_flags))
        client.save({"conanfile.py": conanfile_py})
        client.run("create .")
        # Dependency - other/0.1
        conanfile_py = textwrap.dedent("""
        from conan import ConanFile

        class OtherConan(ConanFile):
            name = "other"
            version = "0.1"

            def package_info(self):
                self.cpp_info.defines = ['DEF3=simple_string']
        """)
        client.save({"conanfile.py": conanfile_py}, clean_first=True)
        client.run("create .")

        # Consumer using PkgConfigDeps and MesonToolchain
        conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.meson import Meson, MesonToolchain
        from conan.tools.gnu import PkgConfigDeps

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1", "other/0.1"

            def layout(self):
                self.folders.build = "build"

            def generate(self):
                deps = PkgConfigDeps(self)
                deps.generate()
                tc = MesonToolchain(self)
                tc.preprocessor_definitions["VAR"] = "VALUE"
                tc.preprocessor_definitions["VAR2"] = "VALUE2"
                tc.generate()

            def build(self):
                meson = Meson(self)
                meson.configure()
                meson.build()
        """)

        meson_build = textwrap.dedent("""
            project('tutorial', 'cpp')
            cxx = meson.get_compiler('cpp')
            hello = dependency('hello', version : '>=0.1')
            other = dependency('other', version : '>=0.1')
            # It's not needed to declare "hello/0.1" as a dependency, only interested in flags
            executable('demo', 'main.cpp', dependencies: [hello, other])
        """)

        main = textwrap.dedent("""
            #include <stdio.h>
            #define STR(x)   #x
            #define SHOW_DEFINE(x) printf("%s=%s", #x, STR(x))
            int main(int argc, char *argv[]) {
                SHOW_DEFINE(VAR);
                SHOW_DEFINE(VAR2);
                SHOW_DEFINE(DEF1);
                SHOW_DEFINE(DEF2);
                SHOW_DEFINE(DEF3);
                return 0;
            }
        """)

        client.save({"conanfile.py": conanfile_py,
                     "meson.build": meson_build,
                     "main.cpp": main},
                    clean_first=True)

        client.run("build . -c 'tools.build:cxxflags=[%s]'" % flags)

        app_name = "demo.exe" if platform.system() == "Windows" else "demo"
        client.run_command(os.path.join("build", app_name))
        assert 'VAR="VALUE' in client.out
        assert 'VAR2="VALUE2"' in client.out
        assert 'DEF1=one_string' in client.out
        assert 'DEF2=other_string' in client.out
        assert 'DEF3=simple_string' in client.out
