import os
import platform
import textwrap
import pathlib
import re
import pytest

from conan.tools.apple.apple import _to_apple_arch, XCRun
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.conftest import tools_locations
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient
from conans.util.runners import conan_run

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
            self.options.rm_safe("fPIC")

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

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


@pytest.mark.tool("meson")
@pytest.mark.skipif(platform.system() != "Darwin", reason="requires Xcode")
@pytest.mark.parametrize("arch, os_, os_version, os_sdk", [
    ('armv8', 'iOS', '17.1', 'iphoneos'),
    ('armv7', 'iOS', '10.0', 'iphoneos'),
    ('x86', 'iOS', '10.0', 'iphonesimulator'),
    ('x86_64', 'iOS', '10.0', 'iphonesimulator'),
    ('armv8' if platform.machine() == "x86_64" else "x86_64", 'Macos', None, None),
    ('armv8' if platform.machine() == "x86_64" else "x86_64", 'Macos', '10.11', None),
])
def test_apple_meson_toolchain_cross_compiling(arch, os_, os_version, os_sdk):
    profile = textwrap.dedent("""
    [settings]
    os = {os}
    {os_version}
    {os_sdk}
    arch = {arch}
    compiler = apple-clang
    compiler.version = 12.0
    compiler.libcxx = libc++
    """)

    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    profile = profile.format(
        os=os_,
        os_version=f"os.version={os_version}" if os_version else "",
        os_sdk="os.sdk = " + os_sdk if os_sdk else "",
        arch=arch)

    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "meson.build": _meson_build,
            "meson_options.txt": _meson_options_txt,
            "hello.h": hello_h,
            "hello.cpp": hello_cpp,
            "main.cpp": app,
            "profile_host": profile})

    t.run("build . --profile:build=default --profile:host=profile_host")

    libhello = os.path.join(t.current_folder, "build", "libhello.a")
    assert os.path.isfile(libhello) is True
    demo = os.path.join(t.current_folder, "build", "demo")
    assert os.path.isfile(demo) is True

    conanfile = ConanFileMock({}, runner=conan_run)
    xcrun = XCRun(conanfile, os_sdk)
    lipo = xcrun.find('lipo')

    t.run_command('"%s" -info "%s"' % (lipo, libhello))
    assert "architecture: %s" % _to_apple_arch(arch) in t.out

    t.run_command('"%s" -info "%s"' % (lipo, demo))
    assert "architecture: %s" % _to_apple_arch(arch) in t.out

    if os_ == "iOS":
        # only check for iOS because one of the macos build variants is usually native
        content = t.load("conan_meson_cross.ini")
        assert "needs_exe_wrapper = true" in content
    elif os_ == "Macos" and not os_version:
        content = t.load("conan_meson_cross.ini")
        assert "'-mmacosx-version-min=" not in content
    elif os_ == "Macos" and os_version:
        # Issue related: https://github.com/conan-io/conan/issues/15459
        content = t.load("conan_meson_cross.ini")
        assert f"'-mmacosx-version-min={os_version}'" in content


@pytest.mark.tool("meson")
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
    client.run("build . %s" % profile_str)
    client.run_command(os.path.join("build", "demo"))
    assert "main _M_IX86 defined" in client.out
    assert "main _MSC_VER19" in client.out
    assert "main _MSVC_LANG2014" in client.out


@pytest.mark.parametrize("arch, expected_arch", [('armv8', 'aarch64'),
                                                 ('armv7', 'arm'),
                                                 ('x86', 'i386'),
                                                 ('x86_64', 'x86_64')])
@pytest.mark.tool("meson")
@pytest.mark.tool("android_ndk")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Android NDK only tested in MacOS for now")
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
    ndk_path = tools_locations["android_ndk"]["system"]["path"][platform.system()]
    profile_host = profile_host.format(
        arch=arch,
        ndk_path=ndk_path
    )

    client = TestClient()
    client.save({"conanfile.py": _conanfile_py,
                 "meson.build": _meson_build,
                 "meson_options.txt": _meson_options_txt,
                 "hello.h": hello_h,
                 "hello.cpp": hello_cpp,
                 "main.cpp": app,
                 "profile_host": profile_host})

    client.run("build . --profile:build=default --profile:host=profile_host")
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


@pytest.mark.parametrize("arch, expected_arch", [('armv8', 'aarch64')])
@pytest.mark.tool("meson")
@pytest.mark.tool("android_ndk")
@pytest.mark.skipif(platform.system() == "Windows", reason="Android NDK only tested on MacOS for now")
def test_android_meson_toolchain_cross_compiling_windows(arch, expected_arch):
    android_abi_prefix = {
        "armv8": "aarch64",
        "armv7": "armv7a",
        "x86": "i686",
        "x86_64": "x86_64"
    }

    android_abi_postfix = "" if arch != "armv7" else "eabi"

    api_level = 21
    ndk_path = os.getenv("TEST_CONAN_ANDROID_NDK")
    profile_host = textwrap.dedent("""
    include(default)

    [settings]
    os = Android
    os.api_level = {api_level}
    arch = {arch}

    [conf]
    tools.android:ndk_path={ndk_path}
    """)
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    profile_host = profile_host.format(
        api_level=api_level,
        arch=arch,
        ndk_path=ndk_path
    )

    clang_path_template = "{ndk_path}/toolchains/llvm/prebuilt/{platform}-x86_64/bin/{android_prefix}-linux-android{android_abi_postfix}{api_level}-{compiler}{extension}"
    expected_c_clang_path = pathlib.PurePath(
        clang_path_template.format(
            ndk_path=ndk_path,
            platform=platform.system().lower(),
            android_prefix=android_abi_prefix[arch],
            android_abi_postfix=android_abi_postfix,
            api_level=api_level,
            compiler="clang",
            extension=".cmd" if platform.system() == "Windows" else ""
        ))
    expected_cpp_clang_path = pathlib.PurePath(
        clang_path_template.format(
            ndk_path=ndk_path,
            platform=platform.system().lower(),
            android_prefix=android_abi_prefix[arch],
            android_abi_postfix=android_abi_postfix,
            api_level=api_level,
            compiler="clang++",
            extension=".cmd" if platform.system() == "Windows" else ""
        )
    )

    client = TestClient()
    client.save({"conanfile.py": _conanfile_py,
                 "meson.build": _meson_build,
                 "meson_options.txt": _meson_options_txt,
                 "hello.h": hello_h,
                 "hello.cpp": hello_cpp,
                 "main.cpp": app,
                 "profile_host": profile_host})

    client.run("build . --profile:build=default --profile:host=profile_host")
    content = client.load(os.path.join("conan_meson_cross.ini"))

    meson_c_path_match = re.search("^c = '(.*)'", content, re.MULTILINE)
    meson_cpp_path_match = re.search("^cpp = '(.*)'", content, re.MULTILINE)
    assert meson_c_path_match is not None
    assert meson_cpp_path_match is not None

    meson_c_path = pathlib.PurePath(meson_c_path_match.groups(1)[0])
    meson_cpp_path = pathlib.PurePath(meson_cpp_path_match.groups(1)[0])

    assert "needs_exe_wrapper = true" in content
    assert meson_c_path == expected_c_clang_path
    assert meson_cpp_path == expected_cpp_clang_path
    assert "Target machine cpu family: {}".format(
        expected_arch if expected_arch != "i386" else "x86") in client.out
    assert "Target machine cpu: {}".format(arch) in client.out
    libhello_name = pathlib.PurePath("libhello.a")
    libhello = pathlib.PurePath(os.path.join(client.current_folder, "build", libhello_name))
    demo = pathlib.PurePath(os.path.join(client.current_folder, "build", "demo"))
    assert os.path.isfile(libhello)
    assert os.path.isfile(demo)

    # Check binaries architecture
    if platform.system() == "Darwin" or platform.system() == "Linux":
        client.run_command('objdump -f "%s"' % libhello)
        assert "architecture: %s" % expected_arch in client.out
