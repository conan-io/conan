import platform
import textwrap

import pytest
from parameterized import parameterized

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_gnutoolchain_universal_binary_support():
    """Test that GnuToolchain now supports universal binaries on macOS"""
    client = TestClient()
    conanfile = (GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                 .with_generator("GnuToolchain"))
    client.save({"conanfile.py": conanfile})

    client.run('install . --name=foo --version=1.0 -s="arch=armv8|x86_64"')

    toolchain = client.load("conangnutoolchain.sh")
    assert "-arch arm64" in toolchain
    assert "-arch x86_64" in toolchain


def test_gnutoolchain_universal_binary_non_macos():
    """Test that GnuToolchain still raises error for universal binaries on non-macOS"""
    client = TestClient()
    conanfile = (GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                 .with_generator("GnuToolchain"))
    client.save({"conanfile.py": conanfile})

    # This should still raise an error on non-macOS platforms
    client.run('create . --name=foo --version=1.0 -s="os=Linux" -s="arch=armv8|x86_64"',
               assert_error=True)
    assert "Universal arch 'armv8|x86_64' is only supported in Apple OSes" in client.out
