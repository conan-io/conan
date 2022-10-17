import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


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
    assert "Xcode.app/Contents/Developer/Platforms/MacOSX.platform" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Xcode")
def test_xcrun_in_tool_requires():
    # https://github.com/conan-io/conan/issues/12260
    client = TestClient()
    tool = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.apple import XCRun
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def package_info(self):
                xcrun = XCRun(self{})
                self.output.info("sdk: %s" % xcrun.sdk)
        """)
    client.save({"br.py": tool.format("")})
    client.run("export br.py br/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.apple import XCRun
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
    client.run("create . pkg/1.0@ -pr:h=./profile_ios -pr:b=default --build")
    assert "br/0.1: sdk: iphoneos15.0" in client.out
    assert "br/0.1: sdk: macosx" not in client.out

    client.save({"br.py": tool.format(", use_target_settings=False")})
    client.run("export br.py br/0.1@")
    client.run("create . pkg/1.0@ -pr:h=./profile_ios -pr:b=default --build")
    assert "br/0.1: sdk: iphoneos15.0" not in client.out
    assert "br/0.1: sdk: macosx" in client.out
