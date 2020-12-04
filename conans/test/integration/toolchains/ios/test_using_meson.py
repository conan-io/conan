import os
import platform
import pytest
import textwrap
import unittest

from parameterized import parameterized

from conans.client.tools.apple import XCRun, apple_deployment_target_flag, to_apple_arch
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient

from conans.test.integration.toolchains.test_meson import get_meson_version


@pytest.mark.toolchain
@pytest.mark.tool_meson
@unittest.skipUnless(platform.system() == "Darwin", "requires Xcode")
@unittest.skipUnless(get_meson_version() >= "0.56.0", "requires meson >= 0.56.0")
class IOSMesonTestCase(unittest.TestCase):

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
            tc.generate()

        def build(self):
            # this will be moved to build helper eventually
            with tools.vcvars(self) if self.settings.compiler == "Visual Studio" else tools.no_op():
                self.run("meson setup --cross-file conan_meson_cross.ini build .")
                self.run("meson compile -C build")
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
        return [("os", self.os),
                ("os.version", self.os_version),
                ("arch", self.arch),
                ("compiler", "apple-clang"),
                ("compiler.version", "12.0"),
                ("compiler.libcxx", "libc++")]

    def env(self):
        cc = self.xcrun.cc
        cxx = self.xcrun.cxx

        cflags = apple_deployment_target_flag(self.os, self.os_version)
        cflags += " -isysroot " + self.xcrun.sdk_path
        cflags += " -arch " + to_apple_arch(self.arch)
        cxxflags = cflags

        return {'CC': cc,
                'CXX': cxx,
                'CFLAGS': cflags,
                'CXXFLAGS': cxxflags}

    def profile(self):
        template = textwrap.dedent("""
            include(default)
            [settings]
            {settings}
            [env]
            {env}
            """)
        settings = '\n'.join(["%s = %s" % (s[0], s[1]) for s in self.settings()])
        env = '\n'.join(["%s = %s" % (k, v) for k, v in self.env().items()])
        return template.format(settings=settings, env=env)

    @parameterized.expand([('armv8', 'iOS', '10.0', 'iphoneos'),
                           ('armv7', 'iOS', '10.0', 'iphoneos'),
                           ('x86', 'iOS', '10.0', 'iphonesimulator'),
                           ('x86_64', 'iOS', '10.0', 'iphonesimulator')
                           ])
    def test_meson_toolchain(self, arch, os_, os_version, sdk):
        self.xcrun = XCRun(None, sdk)
        self.arch = arch
        self.os = os_
        self.os_version = os_version

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
        self.assertIn("architecture: %s" % to_apple_arch(self.arch), self.t.out)

        self.t.run_command('"%s" -info "%s"' % (lipo, demo))
        self.assertIn("architecture: %s" % to_apple_arch(self.arch), self.t.out)
