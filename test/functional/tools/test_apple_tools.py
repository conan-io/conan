import platform
import re
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Xcode")
def test_xcrun():
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.apple import XCRun

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            def build(self):
                sdk_path = XCRun(self).sdk_path
                self.output.info(sdk_path)
        """)
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create .")
    assert "MacOSX" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Xcode")
def test_xcrun_in_tool_requires():
    # https://github.com/conan-io/conan/issues/12260
    client = TestClient()
    tool = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.apple import XCRun
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def package_info(self):
                xcrun = XCRun(self{})
                self.output.info("sdk: %s" % xcrun.sdk_path)
        """)
    client.save({"br.py": tool.format(", use_settings_target=True")})
    client.run("export br.py --name=br --version=0.1")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            tool_requires = "br/0.1"
        """)

    profile_ios = textwrap.dedent("""
        include(default)
        [settings]
        os=iOS
        os.version=15.4
        os.sdk=iphoneos
        os.sdk_version=15.0
        arch=armv8
    """)

    client.save({"conanfile.py": conanfile, "profile_ios": profile_ios})
    client.run("create . --name=pkg --version=1.0 -pr:h=./profile_ios -pr:b=default --build='*'")
    assert re.search("sdk:.*iPhoneOS", str(client.out))
    assert not re.search("sdk:.*MacOSX", str(client.out))

    client.save({"br.py": tool.format("")})
    client.run("export br.py --name=br --version=0.1")
    client.run("create . --name=pkg --version=1.0 -pr:h=./profile_ios -pr:b=default --build='*'")
    assert not re.search("sdk:.*iPhoneOS", str(client.out))
    assert re.search("sdk:.*MacOSX", str(client.out))


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Xcode")
def test_xcrun_in_required_by_tool_requires():
    """
    ConanCenter case, most typical, openssl builds with autotools so needs the sysroot
    and is a require by cmake so in the build context it needs the settings_build, not
    the settings_target, that's why the use_settings_target default is False
    """
    client = TestClient()

    openssl = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.apple import XCRun
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def build(self):
                xcrun = XCRun(self)
                self.output.info("sdk for building openssl: %s" % xcrun.sdk_path)
        """)

    consumer = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            tool_requires = "cmake/1.0"
        """)

    profile_ios = textwrap.dedent("""
        include(default)
        [settings]
        os=iOS
        os.version=15.4
        os.sdk=iphoneos
        os.sdk_version=15.0
        arch=armv8
    """)

    client.save({"cmake.py": GenConanfile("cmake", "1.0").with_requires("openssl/1.0"),
                 "openssl.py": openssl,
                 "consumer.py": consumer,
                 "profile_ios": profile_ios})

    client.run("export openssl.py --name=openssl --version=1.0")
    client.run("export cmake.py")
    client.run("create consumer.py --name=consumer --version=1.0 -pr:h=./profile_ios -pr:b=default --build='*'")

    assert re.search("sdk for building openssl:.*MacOSX", str(client.out))
