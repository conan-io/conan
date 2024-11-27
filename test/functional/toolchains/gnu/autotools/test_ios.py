import platform
import textwrap

import pytest

from conan.tools.build import load_toolchain_args
from conan.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Xcode")
@pytest.mark.tool("cmake")
@pytest.mark.tool("autotools")
def test_ios():
    profile = textwrap.dedent("""
        include(default)
        [settings]
        os=iOS
        os.sdk=iphoneos
        os.version=12.0
        arch=armv8
        """)

    client = TestClient(path_with_spaces=False)
    client.save({"ios-armv8": profile}, clean_first=True)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.run("create . --profile:build=default --profile:host=ios-armv8 -tf=\"\"")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
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
                 "ios-armv8": profile}, clean_first=True)
    client.run("build . --profile:build=default --profile:host=ios-armv8")
    client.run_command("lipo -info main")
    assert "Non-fat file: main is architecture: arm64" in client.out

    client.run_command("vtool -show-build main")
    assert "platform IOS" in client.out
    assert "minos 12.0" in client.out

    conanbuild = load_toolchain_args(client.current_folder)
    configure_args = conanbuild["configure_args"]
    make_args = conanbuild["make_args"]
    autoreconf_args = conanbuild["autoreconf_args"]
    build_arch = client.api.profiles.get_profile([client.api.profiles.get_default_build()]).settings['arch']
    build_arch = "aarch64" if build_arch == "armv8" else build_arch
    assert configure_args == "--prefix=/ '--bindir=${prefix}/bin' '--sbindir=${prefix}/bin' " \
                             "'--libdir=${prefix}/lib' '--includedir=${prefix}/include' " \
                             "'--oldincludedir=${prefix}/include' '--datarootdir=${prefix}/res' " \
                             f"--host=aarch64-apple-ios --build={build_arch}-apple-darwin"
    assert make_args == ""
    assert autoreconf_args == "--force --install"
