import platform
import textwrap

import pytest
from parameterized import parameterized

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@parameterized.expand(["MesonToolchain", "BazelToolchain"])
def test_create_universal_binary(toolchain):
    client = TestClient()
    conanfile = (GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                 .with_generator(toolchain))
    client.save({"conanfile.py": conanfile})

    client.run('create . --name=foo --version=1.0 -s="arch=armv8|armv8.3|x86_64"',
               assert_error=True)
    assert (f"Error in generator '{toolchain}': "
            f"Universal binaries not supported by toolchain.") in client.out


@parameterized.expand(["AutotoolsToolchain", "GnuToolchain"])
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_toolchain_universal_binary_support(toolchain):
    """Test that toolchain now supports universal binaries on macOS"""
    client = TestClient()
    conanfile = (GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                 .with_generator(toolchain))
    client.save({"conanfile.py": conanfile})

    client.run('install . --name=foo --version=1.0 -s="arch=armv8|x86_64"')

    script_name = f"conan{toolchain.lower()}.sh"
    toolchain_content = client.load(script_name)
    assert "-arch arm64" in toolchain_content
    assert "-arch x86_64" in toolchain_content
    # Verify isysroot flag is NOT present when sdk_path is not configured
    assert "-isysroot" not in toolchain_content


@parameterized.expand(["AutotoolsToolchain", "GnuToolchain"])
def test_toolchain_universal_binary_non_macos(toolchain):
    """Test that toolchain still raises error for universal binaries on non-macOS"""
    client = TestClient()
    conanfile = (GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                 .with_generator(toolchain))
    client.save({"conanfile.py": conanfile})

    # This should still raise an error on non-macOS platforms
    client.run('create . --name=foo --version=1.0 -s="os=Linux" -s="arch=armv8|x86_64"',
               assert_error=True)
    assert "Universal arch 'armv8|x86_64' is only supported in Apple OSes" in client.out


@parameterized.expand(["AutotoolsToolchain", "GnuToolchain"])
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_toolchain_universal_binary_with_sdk_path(toolchain):
    """Test that toolchain sets isysroot when sdk_path is configured for universal binaries"""
    client = TestClient()
    conanfile = (GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                 .with_generator(toolchain))
    client.save({"conanfile.py": conanfile})

    client.run('install . --name=foo --version=1.0 -s="arch=armv8|x86_64" -c="tools.apple:sdk_path=mysdkpath"')

    script_name = f"conan{toolchain.lower()}.sh"
    toolchain_content = client.load(script_name)

    assert "-arch arm64" in toolchain_content
    assert "-arch x86_64" in toolchain_content

    assert "-isysroot" in toolchain_content
    assert "mysdkpath" in toolchain_content


def test_create_universal_binary_test_package_folder():
    # https://github.com/conan-io/conan/issues/18820
    # While multi-arch is Darwin specific, this was a cmake_layout issue, so it can be
    # tested in any platform
    c = TestClient()
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class mylibraryTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def layout(self):
                cmake_layout(self)

            def test(self):
                pass
            """)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("arch"),
            "test_package/conanfile.py": test_conanfile})

    c.run('create . -s="arch=armv8|x86_64"')
    c.run("list *:*")
    assert "arch: armv8|x86_64" in c.out
