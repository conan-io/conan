import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Fails on windows")
def test_crossbuild_windows_incomplete():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            def build(self):
                # using python --version as it does not depend on shell
                self.run("python --version")
            """)
    build_profile = textwrap.dedent("""
        [settings]
        arch=x86_64
    """)
    client.save({"conanfile.py": conanfile, "build_profile": build_profile})
    client.run("create . -pr:b=build_profile", assert_error=True)
    assert "The 'build' profile must have a 'os' declared" in client.out

    build_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    client.save({"conanfile.py": conanfile, "build_profile": build_profile})
    client.run("create . -pr:b=build_profile")
    assert "Python" in client.out
