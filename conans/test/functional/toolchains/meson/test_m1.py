import os
import platform
import sys
import textwrap
import unittest

import pytest

from conans.client.tools.apple import XCRun
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient


@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() != "Darwin", reason="requires Xcode")
class M1MesonTestCase(unittest.TestCase):

    _conanfile_py = textwrap.dedent("""
    from conans import ConanFile, tools
    from conan.tools.meson import Meson, MesonToolchain


    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

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
    add_global_arguments('-DSTRING_DEFINITION="' + get_option('STRING_DEFINITION') + '"',
                         language : 'cpp')
    hello = library('hello', 'hello.cpp')
    executable('demo', 'main.cpp', link_with: hello)
    """)

    _meson_options_txt = textwrap.dedent("""
    option('STRING_DEFINITION', type : 'string', description : 'a string option')
    """)

    def settings(self):
        return [("os", "Macos"),
                ("arch", "armv8"),
                ("compiler", "apple-clang"),
                ("compiler.version", "12.0"),
                ("compiler.libcxx", "libc++")]

    def profile(self):
        template = textwrap.dedent("""
            include(default)
            [settings]
            {settings}
            """)
        settings = '\n'.join(["%s = %s" % (s[0], s[1]) for s in self.settings()])
        return template.format(settings=settings)

    def test_meson_toolchain(self):
        self.xcrun = XCRun(None)

        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t = TestClient()

        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "meson_options.txt": self._meson_options_txt,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "main.cpp": app,
                     "profile_host": self.profile()})

        self.t.run("install . --profile:build=default --profile:host=profile_host")

        self.t.run("build .")

        libhello = os.path.join(self.t.current_folder, "build", "libhello.a")
        self.assertTrue(os.path.isfile(libhello))
        demo = os.path.join(self.t.current_folder, "build", "demo")
        self.assertTrue(os.path.isfile(demo))

        lipo = self.xcrun.find('lipo')

        self.t.run_command('"%s" -info "%s"' % (lipo, libhello))
        self.assertIn("architecture: arm64", self.t.out)

        self.t.run_command('"%s" -info "%s"' % (lipo, demo))
        self.assertIn("architecture: arm64", self.t.out)
