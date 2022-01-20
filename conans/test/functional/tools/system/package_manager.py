import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_apt_get
@pytest.mark.skipif(platform.system() != "Linux", reason="Requires apt")
def test_apt_check():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.system import Apt
        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                apt = Apt(self)
                not_installed = apt.check(["non-existing1", "non-existing2"])
                print("missing:", not_installed)
        """)})
    client.run("create . test/1.0@ -c tools.system.package_manager:tool=apt-get -s:b arch=armv8 "
               "-s:h arch=x86")
    assert "missing: ['non-existing1:i386', 'non-existing2:i386']" in client.out


@pytest.mark.tool_brew
@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires brew")
def test_brew_check():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.system import Brew
        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                brew = Brew(self)
                not_installed = brew.check(["non-existing1", "non-existing2"])
                print("missing:", not_installed)
        """)})
    client.run("create . test/1.0@")
    assert "missing: ['non-existing1', 'non-existing2']" in client.out
