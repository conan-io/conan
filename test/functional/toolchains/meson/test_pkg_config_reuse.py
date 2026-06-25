import os

import pytest
import textwrap

from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.tools import TestClient
from test.functional.toolchains.meson._base import check_binary


@pytest.mark.tool("ninja")
@pytest.mark.tool("meson")
@pytest.mark.tool("pkg_config")
class TestMesonPkgConfig:
    _conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import Meson, MesonToolchain


    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        generators = "PkgConfigDeps"
        requires = "hello/0.1"

        def layout(self):
            self.folders.build = "build"

        def generate(self):
            tc = MesonToolchain(self)
            tc.generate()

        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build()
    """)

    _meson_build = textwrap.dedent("""
    project('tutorial', 'cpp')
    hello = dependency('hello', version : '>=0.1')
    executable('demo', 'main.cpp', dependencies: hello)
    """)

    def test_reuse(self):
        t = TestClient()
        t.run("new cmake_lib -d name=hello -d version=0.1")
        t.run("create . -tf=\"\"")

        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
        # Prepare the actual consumer package
        t.save({"conanfile.py": self._conanfile_py,
                "meson.build": self._meson_build,
                "main.cpp": app},
               clean_first=True)

        # Build in the cache
        t.run("build .")
        t.run_command(os.path.join("build", "demo"))

        assert "Hello World Release!" in t.out

        check_binary(t)
