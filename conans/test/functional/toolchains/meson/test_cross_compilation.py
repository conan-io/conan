import os
import platform
import sys
import textwrap

import pytest

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


@pytest.mark.parametrize("arch, os_, os_version, sdk", [
    ('armv8', 'iOS', '10.0', 'iphoneos'),
    ('armv7', 'iOS', '10.0', 'iphoneos'),
    ('x86', 'iOS', '10.0', 'iphonesimulator'),
    ('x86_64', 'iOS', '10.0', 'iphonesimulator'),
    ('armv8', 'Macos', None, None)  # MacOS M1
])
@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() != "Darwin", reason="requires Xcode")
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

    # only check for iOS because one of the macos build variants is usually native
    if os_ == "iOS":
        content = t.load("conan_meson_cross.ini")
        assert "needs_exe_wrapper = true" in content


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


@pytest.mark.parametrize("arch, expected_arch", [('armv8', 'aarch64'),
                                                 ('armv7', 'arm'),
                                                 ('x86', 'i386'),
                                                 ('x86_64', 'x86_64')])
@pytest.mark.tool_meson
@pytest.mark.tool_android_ndk
@pytest.mark.skipif(platform.system() != "Darwin", reason="Android NDK only tested in MacOS for now")
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
def test_android_meson_toolchain_cross_compiling(arch, expected_arch):
    profile_host = textwrap.dedent("""
    include(default)

    [settings]
    os = Android
    os.api_level = 21
    arch = {arch}

    [conf]
    tools.android:ndk_path={ndk_path}
    """)
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    profile_host = profile_host.format(
        arch=arch,
        ndk_path=os.getenv("TEST_CONAN_ANDROID_NDK")
    )

    client = TestClient()
    client.save({"conanfile.py": _conanfile_py,
                 "meson.build": _meson_build,
                 "meson_options.txt": _meson_options_txt,
                 "hello.h": hello_h,
                 "hello.cpp": hello_cpp,
                 "main.cpp": app,
                 "profile_host": profile_host})

    client.run("install . --profile:build=default --profile:host=profile_host")
    client.run("build .")
    content = client.load(os.path.join("conan_meson_cross.ini"))
    assert "needs_exe_wrapper = true" in content
    assert "Target machine cpu family: {}".format(expected_arch if expected_arch != "i386" else "x86") in client.out
    assert "Target machine cpu: {}".format(arch) in client.out
    libhello_name = "libhello.a" if platform.system() != "Windows" else "libhello.lib"
    libhello = os.path.join(client.current_folder, "build", libhello_name)
    demo = os.path.join(client.current_folder, "build", "demo")
    assert os.path.isfile(libhello)
    assert os.path.isfile(demo)

    # Check binaries architecture
    if platform.system() == "Darwin":
        client.run_command('objdump -f "%s"' % libhello)
        assert "architecture: %s" % expected_arch in client.out
