import textwrap
import platform

import pytest

from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.toolchains.meson._base import TestMesonBase
from conans.test.utils.tools import TestClient


class TestMesonToolchainAndGnuFlags(TestMesonBase):

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix only")
    def test_mesontoolchain_using_gnu_deps_flags(self):
        client = TestClient(path_with_spaces=False)
        client.run("new hello/0.1 -s")
        client.run("create . hello/0.1@ %s" % self._settings_str)
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.meson import Meson, MesonToolchain
        from conan.tools.gnu import get_gnu_deps_flags


        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"

            def layout(self):
                self.folders.build = "build"

            def generate(self):
                # Get GNU flags from all the dependencies
                cflags, cxxflags, cpp_flags, libs, ldflags = get_gnu_deps_flags(self)

                tc = MesonToolchain(self)
                # Extend flags to MesonToolchain
                tc.c_args.extend(cpp_flags)
                tc.cpp_args.extend(cpp_flags)
                tc.c_link_args.extend(ldflags)
                tc.cpp_link_args.extend(ldflags)
                tc.generate()

            def build(self):
                meson = Meson(self)
                meson.configure()
                meson.build()
        """)

        meson_build = textwrap.dedent("""
        project('tutorial', 'cpp')
        cxx = meson.get_compiler('cpp')
        hello = cxx.find_library('hello', required: true)
        executable('demo', 'main.cpp', dependencies: hello)
        """)

        client.save({"conanfile.py": conanfile_py,
                     "meson.build": meson_build,
                     "main.cpp": app},
                    clean_first=True)

        client.run("install . %s" % self._settings_str)
        client.run("build .")
        assert "[2/2] Linking target demo" in client.out
