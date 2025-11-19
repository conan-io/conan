import os
import textwrap

import pytest

from conan.test.assets.sources import gen_function_cpp, gen_function_h
from conan.test.utils.tools import TestClient
from test.functional.toolchains.meson._base import check_binary


class TestMesonPreprocessorDefinitionsTest:
    _conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import Meson, MesonToolchain


    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def layout(self):
            self.folders.build = "build"

        def generate(self):
            tc = MesonToolchain(self)
            tc.preprocessor_definitions["TEST_DEFINITION1"] = "TestPpdValue1"
            tc.preprocessor_definitions["TEST_DEFINITION2"] = "TestPpdValue2"
            tc.generate()

        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build()
    """)

    _meson_build = textwrap.dedent("""
    project('tutorial', 'cpp')
    hello = library('hello', 'hello.cpp')
    executable('demo', 'main.cpp', link_with: hello)
    """)

    @pytest.mark.tool("ninja")
    @pytest.mark.tool("meson")
    def test_build(self):
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello",
                                     preprocessor=["TEST_DEFINITION1", "TEST_DEFINITION2"])
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        t = TestClient()
        t.save({"conanfile.py": self._conanfile_py,
                "meson.build": self._meson_build,
                "hello.h": hello_h,
                "hello.cpp": hello_cpp,
                "main.cpp": app})

        t.run("install .")

        content = t.load("conan_meson_native.ini")

        assert "[built-in options]" in content
        assert "buildtype = 'release'" in content

        t.run("build .")
        t.run_command(os.path.join("build", "demo"))

        assert "hello: Release!" in t.out
        assert "TEST_DEFINITION1: TestPpdValue1" in t.out
        assert "TEST_DEFINITION2: TestPpdValue2" in t.out

        check_binary(t)
