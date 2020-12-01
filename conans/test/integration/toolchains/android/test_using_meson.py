import os
import pytest
import platform
import textwrap
import unittest

from parameterized import parameterized

from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient

from conans.test.integration.toolchains.test_meson import get_meson_version


@pytest.mark.toolchain
@pytest.mark.tool_meson
@unittest.skipUnless(get_meson_version() >= "0.56.0", "requires meson >= 0.56.0")
class AndroidToolchainMesonTestCase(unittest.TestCase):

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

    def setUp(self):
        if not self._ndk:
            raise unittest.SkipTest("requires Android NDK")

    @property
    def _ndk(self):
        return os.getenv("ANDROID_NDK")

    @property
    def _ndk_bin(self):
        host = "%s-x86_64" % platform.system().lower()
        return os.path.join(self._ndk, "toolchains", "llvm", "prebuilt", host, "bin")

    @property
    def _api_level(self):
        return "21"

    def settings(self):
        return [("os", "Android"),
                ("os.api_level", self._api_level),
                ("arch", self.arch),
                ("compiler", "clang"),
                ("compiler.version", "9"),
                ("compiler.libcxx", "c++_shared")]

    @property
    def _target(self):
        return {'armv7': 'armv7a-linux-androideabi%s',
                'armv8': 'aarch64-linux-android%s',
                'x86': 'i686-linux-android%s',
                'x86_64': 'x86_64-linux-android%s'}.get(self.arch) % self._api_level

    @property
    def _prefix(self):
        return {'armv7': 'arm-linux-androideabi',
                'armv8': 'aarch64-linux-android',
                'x86': 'i686-linux-android',
                'x86_64': 'x86_64-linux-android'}.get(self.arch)

    def _tool(self, name):
        return os.path.join(self._ndk_bin, "%s-%s" % (self._prefix, name))

    def env(self):
        cc = os.path.join(self._ndk_bin, "clang")
        cxx = os.path.join(self._ndk_bin, "clang++")
        ar = self._tool('ar')
        cflags = '--target=%s' % self._target
        cxxflags = '--target=%s' % self._target

        return {'CC': cc,
                'CXX': cxx,
                'AR': ar,
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

    @parameterized.expand([('armv8', 'aarch64', 'ELF64', 'AArch64'),
                           ('armv7', 'arm', 'ELF32', 'ARM'),
                           ('x86', 'i386', 'ELF32', 'Intel 80386'),
                           ('x86_64', 'i386:x86-64', 'ELF64', 'Advanced Micro Devices X86-64')
                           ])
    def test_meson_toolchain(self, arch, expected_arch, expected_class, expected_machine):
        self.arch = arch

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

        readelf = self._tool('readelf')
        objdump = self._tool('objdump')

        self.t.run_command('"%s" -f "%s"' % (objdump, libhello))
        self.assertIn("architecture: %s" % expected_arch, self.t.out)

        self.t.run_command('"%s" -h "%s"' % (readelf, demo))
        self.assertIn("Class:                             %s" % expected_class, self.t.out)
        self.assertIn("OS/ABI:                            UNIX - System V", self.t.out)
        self.assertIn("Machine:                           %s" % expected_machine, self.t.out)
