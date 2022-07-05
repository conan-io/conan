import textwrap

from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.toolchains.meson._base import TestMesonBase
from conans.test.utils.tools import TestClient


class TestMesonToolchainAndGnuFlags(TestMesonBase):

    def test_mesontoolchain_using_gnu_deps_flags(self):
        client = TestClient(path_with_spaces=False)
        client.run("new hello/0.1 -s")
        client.run("create . hello/0.1@ %s" % self._settings_str)
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.meson import Meson

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "MesonDeps", "MesonToolchain"

            def layout(self):
                self.folders.build = "build"

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
