import os
import textwrap

from conan.test.assets.sources import gen_function_cpp, gen_function_h
from test.functional.toolchains.meson._base import TestMesonBase


class MesonPreprocessorDefinitionsTest(TestMesonBase):
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

    def test_build(self):
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello",
                                     preprocessor=["TEST_DEFINITION1", "TEST_DEFINITION2"])
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "main.cpp": app})

        self.t.run("install .")

        content = self.t.load("conan_meson_native.ini")

        self.assertIn("[built-in options]", content)
        self.assertIn("buildtype = 'release'", content)

        self.t.run("build .")
        self.t.run_command(os.path.join("build", "demo"))

        self.assertIn("hello: Release!", self.t.out)
        self.assertIn("TEST_DEFINITION1: TestPpdValue1", self.t.out)
        self.assertIn("TEST_DEFINITION2: TestPpdValue2", self.t.out)

        self._check_binary()
