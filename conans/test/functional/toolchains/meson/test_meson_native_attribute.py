import os
import platform
import textwrap

import pytest

from conan.tools.apple.apple import _to_apple_arch, XCRun
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient
from conans.util.runners import conan_run


@pytest.mark.tool("meson")
@pytest.mark.skipif(platform.system() != "Darwin", reason="requires OSX")
def test_apple_meson_toolchain_cross_compiling():
    arch = 'armv8' if platform.machine() == "x86_64" else "x86_64"
    profile = textwrap.dedent(f"""
    [settings]
    os = Macos
    arch = {arch}
    compiler = apple-clang
    compiler.version = 12.0
    compiler.libcxx = libc++
    """)
    conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import Meson, MesonToolchain
    from conan.tools.build import cross_building

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
            # Forcing to create the native context too
            if cross_building(self):
                tc = MesonToolchain(self, native=True)
                tc.generate()

        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build()
    """)
    meson_build = textwrap.dedent("""
    project('tutorial', 'cpp')
    hello = library('hello', 'hello.cpp')
    # Even cross-building the library, we want to create an executable using only the native context
    executable('mygen', 'mygen.cpp', native: true)
    """)
    my_gen_cpp = textwrap.dedent("""
    #include <iostream>
    int main() {
        std::cout << "Hello World!";
        return 0;
    }
    """)
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello")
    client = TestClient()
    client.save({"conanfile.py": conanfile_py,
                 "meson.build": meson_build,
                 "hello.h": hello_h,
                 "hello.cpp": hello_cpp,
                 "mygen.cpp": my_gen_cpp,
                 "profile_host": profile})
    client.run("build . --profile:build=default --profile:host=profile_host")
    libhello = os.path.join(client.current_folder, "build", "libhello.a")
    assert os.path.isfile(libhello) is True
    # Now, ensuring that we can run the mygen executable
    mygen = os.path.join(client.current_folder, "build", "mygen")
    client.run_command(f"'{mygen}'")
    assert "Hello" in client.out
    # Extra check for lib arch
    conanfile = ConanFileMock({}, runner=conan_run)
    xcrun = XCRun(conanfile)
    lipo = xcrun.find('lipo')
    client.run_command('"%s" -info "%s"' % (lipo, libhello))
    assert "architecture: %s" % _to_apple_arch(arch) in client.out
