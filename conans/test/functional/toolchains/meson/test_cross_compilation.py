import os
import platform
import sys
import textwrap
import unittest

import pytest
from parameterized import parameterized

from conans.client.tools.apple import XCRun, to_apple_arch
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient

_conanfile_py = textwrap.dedent("""
from conan import ConanFile
from conan.tools.meson import Meson, MesonToolchain


class App(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    def layout(self):
        self.folders.build = "build"

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


@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() != "Darwin", reason="requires Xcode")
@pytest.mark.parametrize("arch, os_, os_version, sdk", [
    ('armv8', 'iOS', '10.0', 'iphoneos'),
    ('armv7', 'iOS', '10.0', 'iphoneos'),
    ('x86', 'iOS', '10.0', 'iphonesimulator'),
    ('x86_64', 'iOS', '10.0', 'iphonesimulator'),
    ('armv8', 'Macos', None, None)  # MacOS M1
])
def test_apple_meson_toolchain_cross_compiling(arch, os_, os_version, sdk):
    profile = textwrap.dedent("""
    include(default)

    [settings]
    os = {os}
    os.version = {os_version}
    os.sdk = {os_sdk}
    arch = {arch}
    compiler = apple-clang
    compiler.version = 12.0
    compiler.libcxx = libc++

    [conf]
    tools.apple:sdk_path={sdk_path}
    """)

    xcrun = XCRun(None, sdk)
    sdk_path = xcrun.sdk_path

    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    profile = profile.format(
        os=os_,
        os_version=os_version,
        os_sdk=sdk,
        arch=arch,
        sdk_path=sdk_path)

    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "meson.build": _meson_build,
            "meson_options.txt": _meson_options_txt,
            "hello.h": hello_h,
            "hello.cpp": hello_cpp,
            "main.cpp": app,
            "profile_host": profile})

    t.run("install . --profile:build=default --profile:host=profile_host")
    t.run("build .")

    libhello = os.path.join(t.current_folder, "build", "libhello.a")
    assert os.path.isfile(libhello) is True
    demo = os.path.join(t.current_folder, "build", "demo")
    assert os.path.isfile(demo) is True

    lipo = xcrun.find('lipo')

    t.run_command('"%s" -info "%s"' % (lipo, libhello))
    assert "architecture: %s" % to_apple_arch(arch) in t.out

    t.run_command('"%s" -info "%s"' % (lipo, demo))
    assert "architecture: %s" % to_apple_arch(arch) in t.out


@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
# for Linux, build for x86 will require a multilib compiler
# for macOS, build for x86 is no longer supported by modern Xcode
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Windows")
def test_windows_cross_compiling_x86():
    meson_build = textwrap.dedent("""
        project('tutorial', 'cpp')
        executable('demo', 'main.cpp')
        """)
    main_cpp = gen_function_cpp(name="main")
    profile_x86 = textwrap.dedent("""
        include(default)
        [settings]
        arch=x86
        """)

    client = TestClient()
    client.save({"conanfile.py": _conanfile_py,
                 "meson.build": meson_build,
                 "main.cpp": main_cpp,
                 "x86": profile_x86})
    profile_str = "--profile:build=default --profile:host=x86"
    client.run("install . %s" % profile_str)
    client.run("build .")
    client.run_command(os.path.join("build", "demo"))

    assert "main _M_IX86 defined" in client.out
    assert "main _MSC_VER19" in client.out
    assert "main _MSVC_LANG2014" in client.out


@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
class AndroidMesonToolchainCrossTestCase(unittest.TestCase):

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
        ldflags = '--target=%s' % self._target

        return {'CC': cc,
                'CXX': cxx,
                'AR': ar,
                'CFLAGS': cflags,
                'CXXFLAGS': cxxflags,
                'LDFLAGS': ldflags}

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
    def test_android_meson_toolchain_cross_compiling(self, arch, expected_arch,
                                                     expected_class, expected_machine):
        self.arch = arch

        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t = TestClient()

        self.t.save({"conanfile.py": _conanfile_py,
                     "meson.build": _meson_build,
                     "meson_options.txt": _meson_options_txt,
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
