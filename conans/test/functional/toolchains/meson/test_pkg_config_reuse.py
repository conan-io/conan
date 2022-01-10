import os

import pytest
import textwrap

from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.toolchains.meson._base import TestMesonBase


@pytest.mark.tool_pkg_config
class MesonPkgConfigTest(TestMesonBase):
    _conanfile_py = textwrap.dedent("""
    from conans import ConanFile, tools
    from conan.tools.meson import Meson, MesonToolchain


    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        generators = "PkgConfigDeps"
        requires = "hello/0.1"

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
        self.t.run("new cmake_lib -d name=hello -d version=0.1")
        self.t.run("create . hello/0.1@ -tf=None")

        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        # Prepare the actual consumer package
        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "main.cpp": app},
                    clean_first=True)

        # Build in the cache
        self.t.run("install .")

        self.t.run("build .")
        self.t.run_command(os.path.join("build", "demo"))

        self.assertIn("Hello World Release!", self.t.out)

        self._check_binary()
