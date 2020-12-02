import os
import platform
import pytest
import textwrap
import unittest

from conans.model.version import Version
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient
from conans.util.files import decode_text
from conans.util.runners import version_runner


def get_meson_version():
    try:
        out = version_runner(["meson", "--version"])
        version_line = decode_text(out).split('\n', 1)[0]
        version_str = version_line.rsplit(' ', 1)[-1]
        return Version(version_str)
    except Exception:
        return Version("0.0.0")


@pytest.mark.toolchain
@pytest.mark.tool_meson
@unittest.skipUnless(get_meson_version() >= "0.56.0", "requires meson >= 0.56.0")
class MesonToolchainTest(unittest.TestCase):
    _conanfile_py = textwrap.dedent("""
    from conans import ConanFile, tools
    from conan.tools.meson import MesonToolchain


    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def toolchain(self):
            tc = MesonToolchain(self)
            tc.definitions["STRING_DEFINITION"] = "Text"
            tc.definitions["TRUE_DEFINITION"] = True
            tc.definitions["FALSE_DEFINITION"] = False
            tc.definitions["INT_DEFINITION"] = 42
            tc.definitions["ARRAY_DEFINITION"] = ["Text1", "Text2"]
            tc.generate()

        def build(self):
            # this will be moved to build helper eventually
            with tools.vcvars(self) if self.settings.compiler == "Visual Studio" else tools.no_op():
                self.run("meson setup --native-file conan_meson_native.ini build .")
                self.run("meson compile -C build")
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

    @unittest.skipUnless(platform.system() == "Darwin", "Only for Apple")
    def test_macosx(self):
        settings = {"compiler": "apple-clang",
                    "compiler.libcxx": "libc++",
                    "compiler.version": "11.0",
                    "arch": "x86_64",
                    "build_type": "Release"}
        self._build(settings)

        self.assertIn("main __x86_64__ defined", self.t.out)
        self.assertIn("main __apple_build_version__", self.t.out)
        self.assertIn("main __clang_major__11", self.t.out)
        self.assertIn("main __clang_minor__0", self.t.out)

    @unittest.skipUnless(platform.system() == "Windows", "Only for windows")
    def test_win32(self):
        settings = {"compiler": "Visual Studio",
                    "compiler.version": "15",
                    "compiler.runtime": "MD",
                    "arch": "x86_64",
                    "build_type": "Release"}
        self._build(settings)

        self.assertIn("main _M_X64 defined", self.t.out)
        self.assertIn("main _MSC_VER19", self.t.out)
        self.assertIn("main _MSVC_LANG2014", self.t.out)

    @unittest.skipUnless(platform.system() == "Linux", "Only for Linux")
    def test_linux(self):
        setttings = {"compiler": "gcc",
                     "compiler.version": "5",
                     "compiler.libcxx": "libstdc++",
                     "arch": "x86_64",
                     "build_type": "Release"}
        self._build(setttings)

        self.assertIn("main __x86_64__ defined", self.t.out)
        self.assertIn("main __GNUC__5", self.t.out)

    def _build(self, settings):
        self.t = TestClient()

        settings_str = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "meson_options.txt": self._meson_options_txt,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "main.cpp": app})

        self.t.run("install . %s" % settings_str)

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
