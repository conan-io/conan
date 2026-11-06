import platform
import re
import textwrap
import os
import pytest
from unittest import mock

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.tools.apple.apple import XCRun
from conan.test.utils.mocks import ConanFileMock, MockSettings
from conan.internal.util.runners import conan_run


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


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires OSX and xcrun tool")
def test_xcrun_sdks():
    def _common_asserts(xcrun_):
        assert xcrun_.cc.endswith('clang')
        assert xcrun_.cxx.endswith('clang++')
        assert xcrun_.ar.endswith('ar')
        assert xcrun_.ranlib.endswith('ranlib')
        assert xcrun_.strip.endswith('strip')
        assert xcrun_.find('lipo').endswith('lipo')
        assert os.path.isdir(xcrun_.sdk_path)

    conanfile = ConanFileMock( runner=conan_run)
    conanfile.settings = MockSettings(
        {"os": "Macos",
         "arch": "x86"})
    xcrun = XCRun(conanfile)
    _common_asserts(xcrun)

    conanfile.settings = MockSettings(
        {"os": "iOS",
         "arch": "x86"})
    xcrun = XCRun(conanfile, sdk='macosx')
    _common_asserts(xcrun)
    # Simulator
    assert "iPhoneOS" not in xcrun.sdk_path

    conanfile.settings = MockSettings(
        {"os": "iOS",
         "os.sdk": "iphoneos",
         "arch": "armv7"})
    xcrun = XCRun(conanfile)
    _common_asserts(xcrun)
    assert "iPhoneOS" in xcrun.sdk_path

    conanfile.settings = MockSettings(
        {"os": "watchOS",
         "os.sdk": "watchos",
         "arch": "armv7"})
    xcrun = XCRun(conanfile)
    _common_asserts(xcrun)
    assert "WatchOS" in xcrun.sdk_path

    # Default one
    conanfile.settings = MockSettings({})
    xcrun = XCRun(conanfile)
    _common_asserts(xcrun)


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
        os.version=15.5
        os.sdk=iphoneos
        os.sdk_version=15.5
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
        os.version=15.5
        os.sdk=iphoneos
        os.sdk_version=15.5
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


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Apple install names")
@pytest.mark.parametrize("install_dir", ["@rpath", "/lib"])
def test_fix_shared_install_name_prefix_library(install_dir):
    """libabc is a prefix of libabcrt (like flatcc / flatccrt): the executable must keep
    pointing at each library, not at whichever matching one is listed first"""
    conanfile = textwrap.dedent(f"""
        import os
        from conan import ConanFile
        from conan.tools.apple import XCRun, fix_apple_shared_install_name
        from conan.tools.files import save

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"

            def package(self):
                xcrun = XCRun(self)
                cmd = f'"{{xcrun.cc}}" -isysroot "{{xcrun.sdk_path}}"'
                lib = os.path.join(self.package_folder, "lib")
                exe = os.path.join(self.package_folder, "bin", "app")
                os.makedirs(lib)
                os.makedirs(os.path.dirname(exe))
                # each library exports its own symbol, so a wrong reference fails at runtime
                for name in ("abc", "abcrt"):
                    save(self, f"{{name}}.c", f"int {{name}}(void){{{{return 1;}}}}")
                    self.run(f'{{cmd}} -dynamiclib {{name}}.c -o "{{lib}}/lib{{name}}.dylib" '
                             f'-install_name {install_dir}/lib{{name}}.dylib')
                save(self, "main.c", "int abc(void);int abcrt(void);"
                                     "int main(void){{return abc()+abcrt()==2?0:1;}}")
                # links against both, like flatcc does
                self.run(f'{{cmd}} main.c -L "{{lib}}" -labc -labcrt -o "{{exe}}" '
                         f'-Wl,-headerpad_max_install_names')
                fix_apple_shared_install_name(self)
        """)
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.py": conanfile})

    # The bug only shows if the longer name is listed first, which depends on the
    # filesystem (APFS hashes names), so force that order
    real_listdir = os.listdir
    with mock.patch("conan.tools.apple.apple.os.listdir",
                    side_effect=lambda p: sorted(real_listdir(p), reverse=True)):
        client.run("create . -tf=")

    exe = os.path.join(client.created_layout().package(), "bin", "app")
    client.run_command(f'otool -L "{exe}"')
    assert client.out.count("@rpath/libabc.dylib") == 1
    assert client.out.count("@rpath/libabcrt.dylib") == 1
    client.run_command(f'"{exe}"')  # dyld would fail if a reference points to the wrong lib


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Apple install names")
@pytest.mark.parametrize("install_dir", ["@rpath", "/lib"])
def test_fix_shared_install_name_prefix_external_library(install_dir):
    """The executable links libabc, which is not part of the package, and libabcrt, which is.
    The reference to libabc is not ours to fix, even if it is a prefix of a packaged library"""
    conanfile = textwrap.dedent(f"""
        import os
        from conan import ConanFile
        from conan.tools.apple import XCRun, fix_apple_shared_install_name
        from conan.tools.files import save

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"

            def package(self):
                xcrun = XCRun(self)
                cmd = f'"{{xcrun.cc}}" -isysroot "{{xcrun.sdk_path}}"'
                external = os.path.join(self.build_folder, "external")
                lib = os.path.join(self.package_folder, "lib")
                exe = os.path.join(self.package_folder, "bin", "app")
                os.makedirs(external)
                os.makedirs(lib)
                os.makedirs(os.path.dirname(exe))
                for name, folder in (("abc", external), ("abcrt", lib)):
                    save(self, f"{{name}}.c", f"int {{name}}(void){{{{return 1;}}}}")
                    self.run(f'{{cmd}} -dynamiclib {{name}}.c -o "{{folder}}/lib{{name}}.dylib" '
                             f'-install_name {install_dir}/lib{{name}}.dylib')
                save(self, "main.c", "int abc(void);int abcrt(void);"
                                     "int main(void){{return abc()+abcrt()==2?0:1;}}")
                self.run(f'{{cmd}} main.c -L "{{external}}" -labc -L "{{lib}}" -labcrt '
                         f'-o "{{exe}}" -Wl,-headerpad_max_install_names')
                fix_apple_shared_install_name(self)
        """)
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.py": conanfile})
    client.run("create . -tf=")

    exe = os.path.join(client.created_layout().package(), "bin", "app")
    client.run_command(f'otool -L "{exe}"')
    assert client.out.count(f"{install_dir}/libabc.dylib") == 1
    assert client.out.count("@rpath/libabcrt.dylib") == 1
