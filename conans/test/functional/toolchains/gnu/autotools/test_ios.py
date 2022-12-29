import platform
import textwrap

import pytest

from conan.tools.files.files import load_toolchain_args
from conans.client.tools.apple import XCRun, to_apple_arch
from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Xcode")
def test_ios():
    xcrun = XCRun(None, sdk='iphoneos')
    cflags = ""
    cflags += " -isysroot " + xcrun.sdk_path
    cflags += " -arch " + to_apple_arch('armv8')
    cxxflags = cflags
    ldflags = cflags

    profile = textwrap.dedent("""
        include(default)
        [settings]
        os=iOS
        os.sdk=iphoneos
        os.version=12.0
        arch=armv8
        [env]
        CC={cc}
        CXX={cxx}
        CFLAGS={cflags}
        CXXFLAGS={cxxflags}
        LDFLAGS={ldflags}
    """).format(cc=xcrun.cc, cxx=xcrun.cxx, cflags=cflags, cxxflags=cxxflags, ldflags=ldflags)

    client = TestClient(path_with_spaces=False)
    client.save({"m1": profile}, clean_first=True)
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("create . --profile:build=default --profile:host=m1 -tf None")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp"
            generators = "AutotoolsToolchain", "AutotoolsDeps"

            def layout(self):
                self.cpp.package.resdirs = ["res"]

            def build(self):
                autotools = Autotools(self)
                autotools.autoreconf()
                autotools.configure()
                autotools.make()
        """)

    client.save({"conanfile.py": conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main,
                 "m1": profile}, clean_first=True)
    client.run("install . --profile:build=default --profile:host=m1")
    client.run("build .")
    client.run_command("lipo -info main")
    assert "Non-fat file: main is architecture: arm64" in client.out
    client.run_command("vtool -show-build main")
    assert "platform IOS" in client.out
    assert "minos 12.0" in client.out

    conanbuild = load_toolchain_args(client.current_folder)
    configure_args = conanbuild["configure_args"]
    make_args = conanbuild["make_args"]
    autoreconf_args = conanbuild["autoreconf_args"]
    build_arch = client.get_default_build_profile().settings['arch']
    build_arch = "aarch64" if build_arch == "armv8" else build_arch
    assert configure_args == "'--prefix=/' '--bindir=${prefix}/bin' '--sbindir=${prefix}/bin' " \
                             "'--libdir=${prefix}/lib' '--includedir=${prefix}/include' " \
                             "'--oldincludedir=${prefix}/include' '--datarootdir=${prefix}/res' " \
                             f"'--host=aarch64-apple-ios' '--build={build_arch}-apple-darwin'"
    assert make_args == ""
    assert autoreconf_args == "'--force' '--install'"
