import os
import platform
import sys
import textwrap

import pytest

from conan.tools.apple.apple import _to_apple_arch, XCRun
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.tools import TestClient
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

_meson_build_objc = textwrap.dedent("""
project('tutorial', 'objc')
executable('demo', 'main.m', link_args: ['-framework', 'Foundation'])
""")


@pytest.mark.tool("meson")
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() != "Darwin", reason="requires Xcode")
def test_apple_meson_toolchain_native_compilation_objective_c():
    t = TestClient()
    arch = t.get_default_host_profile().settings['arch']
    profile = textwrap.dedent(f"""
    [settings]
    os = Macos
    arch = {arch}
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
    t.save({"conanfile.py": _conanfile_py,
            "meson.build": _meson_build_objc,
            "main.m": app,
            "macos_pr": profile})

    t.run("build . -pr macos_pr")
    t.run_command("./demo", cwd=os.path.join(t.current_folder, "build"))
    assert "Hello, World!" in t.out


@pytest.mark.parametrize("arch, os_, os_version, sdk", [
    ('armv8', 'iOS', '10.0', 'iphoneos'),
    ('armv7', 'iOS', '10.0', 'iphoneos'),
    ('x86', 'iOS', '10.0', 'iphonesimulator'),
    ('x86_64', 'iOS', '10.0', 'iphonesimulator'),
    ('armv8', 'Macos', '11.0', None)  # Apple Silicon
])
@pytest.mark.tool("meson")
@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.skipif(platform.system() != "Darwin", reason="requires Xcode")
def test_apple_meson_toolchain_cross_compiling_and_objective_c(arch, os_, os_version, sdk):
    profile = textwrap.dedent("""
    include(default)

    [settings]
    os = {os}
    os.version = {os_version}
    {os_sdk}
    arch = {arch}
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
    profile = profile.format(
        os=os_,
        os_version=os_version,
        os_sdk=f'os.sdk = {sdk}' if sdk else '',
        arch=arch)

    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "meson.build": _meson_build_objc,
            "main.m": app,
            "profile_host": profile})

    t.run("build . --profile:build=default --profile:host=profile_host")
    assert "Objective-C compiler for the host machine: clang" in t.out

    demo = os.path.join(t.current_folder, "build", "demo")
    assert os.path.isfile(demo) is True

    conanfile = ConanFileMock({}, runner=conan_run)
    xcrun = XCRun(conanfile, sdk)
    lipo = xcrun.find('lipo')
    t.run_command('"%s" -info "%s"' % (lipo, demo))
    assert "architecture: %s" % _to_apple_arch(arch) in t.out
