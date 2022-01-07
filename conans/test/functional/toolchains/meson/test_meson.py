import os
import textwrap

from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.functional.toolchains.meson._base import TestMesonBase


class MesonToolchainTest(TestMesonBase):
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
            tc.project_options["STRING_DEFINITION"] = "Text"
            tc.project_options["TRUE_DEFINITION"] = True
            tc.project_options["FALSE_DEFINITION"] = False
            tc.project_options["INT_DEFINITION"] = 42
            tc.project_options["ARRAY_DEFINITION"] = ["Text1", "Text2"]
            tc.generate()

        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build(target='hello')
            meson.build(target='demo')
    """)

    _meson_options_txt = textwrap.dedent("""
    option('STRING_DEFINITION', type : 'string', description : 'a string option')
    option('INT_DEFINITION', type : 'integer', description : 'an integer option', value: 0)
    option('FALSE_DEFINITION', type : 'boolean', description : 'a boolean option (false)')
    option('TRUE_DEFINITION', type : 'boolean', description : 'a boolean option (true)')
    option('ARRAY_DEFINITION', type : 'array', description : 'an array option')
    option('HELLO_MSG', type : 'string', description : 'message to print')
    """)

    _meson_build = textwrap.dedent("""
    project('tutorial', 'cpp')
    add_global_arguments('-DSTRING_DEFINITION="' + get_option('STRING_DEFINITION') + '"',
                         language : 'cpp')
    add_global_arguments('-DHELLO_MSG="' + get_option('HELLO_MSG') + '"', language : 'cpp')
    hello = library('hello', 'hello.cpp')
    executable('demo', 'main.cpp', link_with: hello)
    """)

    def test_build(self):
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "meson_options.txt": self._meson_options_txt,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "main.cpp": app})

        self.t.run("install . %s" % self._settings_str)

        content = self.t.load("conan_meson_native.ini")

        self.assertIn("[project options]", content)
        self.assertIn("STRING_DEFINITION = 'Text'", content)
        self.assertIn("TRUE_DEFINITION = true", content)
        self.assertIn("FALSE_DEFINITION = false", content)
        self.assertIn("INT_DEFINITION = 42", content)
        self.assertIn("ARRAY_DEFINITION = ['Text1', 'Text2']", content)

        self.assertIn("[built-in options]", content)
        self.assertIn("buildtype = 'release'", content)

        self.t.run("build .")
        self.t.run_command(os.path.join("build", "demo"))

        self.assertIn("hello: Release!", self.t.out)
        self.assertIn("STRING_DEFINITION: Text", self.t.out)

        self._check_binary()
