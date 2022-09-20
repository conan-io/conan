import platform
import textwrap

import pytest
import six

from conans.test.utils.tools import TestClient


@pytest.mark.tool_apt_get
@pytest.mark.skipif(platform.system() != "Linux", reason="Requires apt")
def test_apt_check():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Apt
        class MyPkg(ConanFile):
            settings = "arch", "os"
            def system_requirements(self):
                apt = Apt(self)
                not_installed = apt.check(["non-existing1", "non-existing2"])
                print("missing:", not_installed)
        """)})
    client.run("create . test/1.0@ -s:b arch=armv8 -s:h arch=x86")
    assert "dpkg-query: no packages found matching non-existing1:i386" in client.out
    assert "dpkg-query: no packages found matching non-existing2:i386" in client.out
    assert "missing: ['non-existing1', 'non-existing2']" in client.out


@pytest.mark.tool_apt_get
@pytest.mark.skipif(platform.system() != "Linux", reason="Requires apt")
def test_apt_install_substitutes():
    client = TestClient()
    conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Apt
        class MyPkg(ConanFile):
            settings = "arch", "os"
            def system_requirements(self):
                # FIXME this is needed because the ci-functional apt-get update fails
                try:
                    self.run("sudo apt-get update")
                except Exception:
                    pass
                apt = Apt(self)
                {}
        """)

    installs = 'apt.install_substitutes(["non-existing1", "non-existing2"], ["non-existing3", "non-existing4"])'
    client.save({"conanfile.py": conanfile_py.format(installs)})
    client.run("create . test/1.0@ -c tools.system.package_manager:mode=install "
               "-c tools.system.package_manager:sudo=True", assert_error=True)

    assert "dpkg-query: no packages found matching non-existing1:amd64" in client.out
    assert "dpkg-query: no packages found matching non-existing2:amd64" in client.out
    assert "dpkg-query: no packages found matching non-existing3:amd64" in client.out
    assert "dpkg-query: no packages found matching non-existing4:amd64" in client.out
    assert "ERROR: while executing system_requirements(): " \
           "None of the installs for the package substitutes succeeded." in client.out

    client.run_command("sudo apt remove nano -yy")
    installs = 'apt.install_substitutes(["non-existing1", "non-existing2"], ["nano"], ["non-existing3"])'
    client.save({"conanfile.py": conanfile_py.format(installs)})
    client.run("create . test/1.0@ -c tools.system.package_manager:mode=install "
               "-c tools.system.package_manager:sudo=True")
    assert "1 newly installed" in client.out


@pytest.mark.tool_apt_get
@pytest.mark.skipif(platform.system() != "Linux", reason="Requires apt")
def test_build_require():
    client = TestClient()
    client.save({"tool_require.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Apt
        class MyPkg(ConanFile):
            settings = "arch", "os"
            def system_requirements(self):
                apt = Apt(self)
                not_installed = apt.check(["non-existing1", "non-existing2"])
                print("missing:", not_installed)
        """)})
    client.run("export tool_require.py tool_require/1.0@")
    client.save({"consumer.py": textwrap.dedent("""
        from conan import ConanFile
        class consumer(ConanFile):
            settings = "arch", "os"
            tool_requires = "tool_require/1.0"
        """)})
    client.run("create consumer.py consumer/1.0@ -s:b arch=armv8 -s:h arch=x86 --build=missing")
    assert "dpkg-query: no packages found matching non-existing1:arm64" in client.out
    assert "dpkg-query: no packages found matching non-existing2:arm64" in client.out
    assert "missing: ['non-existing1', 'non-existing2']" in client.out


@pytest.mark.tool_brew
@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires brew")
def test_brew_check():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Brew
        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                brew = Brew(self)
                not_installed = brew.check(["non-existing1", "non-existing2"])
                print("missing:", not_installed)
        """)})
    client.run("create . test/1.0@")
    assert "missing: ['non-existing1', 'non-existing2']" in client.out


@pytest.mark.tool_brew
@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires brew")
@pytest.mark.skip(reason="brew update takes a lot of time")
def test_brew_install_check_mode():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Brew
        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                brew = Brew(self)
                brew.install(["non-existing1", "non-existing2"])
        """)})
    client.run("create . test/1.0@", assert_error=True)
    assert "System requirements: 'non-existing1, non-existing2' are missing but " \
           "can't install because tools.system.package_manager:mode is 'check'" in client.out


@pytest.mark.tool_brew
@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires brew")
@pytest.mark.skip(reason="brew update takes a lot of time")
def test_brew_install_install_mode():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Brew
        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                brew = Brew(self)
                brew.install(["non-existing1", "non-existing2"])
        """)})
    client.run("create . test/1.0@ -c tools.system.package_manager:mode=install", assert_error=True)
    assert "Error: No formulae found in taps." in client.out
