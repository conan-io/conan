import platform
import textwrap

import pytest

from conan.tools.files.files import load_toolchain_args
from conans.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.apple import XCRun
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Xcode")
@pytest.mark.tool("cmake")
@pytest.mark.tool("autotools")
def test_ios():
    xcrun = XCRun(None, sdk='iphoneos')
    sdk_path = xcrun.sdk_path

    profile = textwrap.dedent("""
        include(default)
        [settings]
        os=iOS
        os.sdk=iphoneos
        os.version=12.0
        arch=armv8

        [conf]
        tools.apple:sdk_path={sdk_path}
    """).format(sdk_path=sdk_path)

    client = TestClient(path_with_spaces=False)
    client.save({"m1": profile}, clean_first=True)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.run("create . --profile:build=default --profile:host=m1 -tf None")

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

            def build(self):
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = Autotools(self)
                autotools.configure()
                autotools.make()
        """)

    client.save({"conanfile.py": conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main,
                 "m1": profile}, clean_first=True)
    client.run("build . --profile:build=default --profile:host=m1")
    client.run_command("./main", assert_error=True)
    assert "Bad CPU type in executable" in client.out
    client.run_command("lipo -info main")
    assert "Non-fat file: main is architecture: arm64" in client.out

    conanbuild = load_toolchain_args(client.current_folder)
    configure_args = conanbuild["configure_args"]
    assert configure_args == "'--disable-shared' '--enable-static' '--with-pic' " \
                             "'--host=aarch64-apple-ios' '--build=x86_64-apple-darwin'"
