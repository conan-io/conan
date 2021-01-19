import os
import textwrap

from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.functional.toolchains.meson._base import TestMesonBase


class MesonToolchainTest(TestMesonBase):

    _conanfile_br = textwrap.dedent("""
    from conans import ConanFile


    class BuildRequires(ConanFile):

        def package_info(self):
            self.env_info.CC = "custom C compiler"
            self.env_info.CXX = "custom CXX compiler"
    """)

    _conanfile_py = textwrap.dedent("""
    from conans import ConanFile, tools
    from conan.tools.meson import Meson, MesonToolchain


    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}
        build_requires = ("br/1.0@",)
        generators = ("virtualenv",)

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

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
    hello = library('hello', 'hello.cpp')
    executable('demo', 'main.cpp', link_with: hello)
    """)

    def test_build(self):
        self.t.save({"conanfile.py": self._conanfile_br})
        self.t.run("create . br/1.0@")

        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello")
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "main.cpp": app}, clean_first=True)

        self.t.run("install . %s" % self._settings_str)

        content = self.t.load("conan_meson_native.ini")

        self.assertIn("c = 'custom C compiler", content)
        self.assertIn("cpp = 'custom CXX compiler", content)
