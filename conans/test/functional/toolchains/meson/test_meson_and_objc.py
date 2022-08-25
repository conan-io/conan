import os
import platform
import sys
import textwrap

import pytest

from conans.client.tools.apple import XCRun, to_apple_arch
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

_meson_build_objc = textwrap.dedent("""
project('tutorial', 'objc')
executable('demo', 'main.m', link_args: ['-framework', 'Foundation'])
""")


@pytest.mark.tool_meson
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() != "Darwin", reason="requires Xcode")
def test_apple_meson_toolchain_native_compilation_objective_c():
    profile = textwrap.dedent("""
    [settings]
    os = Macos
    arch = x86_64
    compiler = apple-clang
    compiler.version = 12.0
    compiler.libcxx = libc++
    """)
    app = textwrap.dedent("""
    #import <Foundation/Foundation.h>

    int main(int argc, const char * argv[]) {
        @autoreleasepool {
            // insert code here...
            NSLog(@"Hello, World!");
        }
        return 0;
    }
    """)
    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "meson.build": _meson_build_objc,
            "main.m": app,
            "macos_pr": profile})

    t.run("install . -pr macos_pr")
    t.run("build .")
    t.run_command("./demo", cwd=os.path.join(t.current_folder, "build"))
    assert "Hello, World!" in t.out


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
def test_apple_meson_toolchain_cross_compiling_and_objective_c(arch, os_, os_version, sdk):
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
    app = textwrap.dedent("""
    #import <Foundation/Foundation.h>

    int main(int argc, const char * argv[]) {
        @autoreleasepool {
            // insert code here...
            NSLog(@"Hello, World!");
        }
        return 0;
    }
    """)
    profile = profile.format(
        os=os_,
        os_version=os_version,
        os_sdk=sdk,
        arch=arch,
        sdk_path=sdk_path)

    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "meson.build": _meson_build_objc,
            "main.m": app,
            "profile_host": profile})

    t.run("install . --profile:build=default --profile:host=profile_host")
    t.run("build .")
    assert "Objective-C compiler for the host machine: clang" in t.out

    demo = os.path.join(t.current_folder, "build", "demo")
    assert os.path.isfile(demo) is True

    lipo = xcrun.find('lipo')
    t.run_command('"%s" -info "%s"' % (lipo, demo))
    assert "architecture: %s" % to_apple_arch(arch) in t.out
