import platform
import textwrap

import pytest

from conan.tools.system.package_manager import Apt, Dnf, Yum, Brew, Pkg, PkgUtil, Chocolatey, Zypper, \
    PacMan
from conans import Settings
from conans.model.conf import Conf
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("sudo, sudo_askpass, expected_str", [
    (True, True, "sudo -A "),
    (True, False, "sudo "),
    (False, True, ""),
    (False, False, ""),
])
def test_sudo_str(sudo, sudo_askpass, expected_str):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:sudo"] = sudo
    conanfile.conf["tools.system.package_manager:sudo_askpass"] = sudo_askpass
    apt = Apt(conanfile)
    assert apt.sudo_str == expected_str


@pytest.mark.parametrize("recommends, recommends_str", [
    (False, "--no-install-recommends "),
    (True, ""),
])
def test_apt_install_recommends(recommends, recommends_str):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    apt = Apt(conanfile)
    apt.install(["package1", "package2"], recommends=recommends)
    assert apt._conanfile.command == "apt-get install -y {}package1 package2".format(recommends_str)


@pytest.mark.parametrize("tool_class", [Apt, Yum, Dnf, Brew, Pkg, PkgUtil, Chocolatey, PacMan, Zypper])
def test_tools_install_mode_check(tool_class):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = tool_class.tool_name
    tool = tool_class(conanfile)
    tool.install(["package1", "package2"])
    assert str(conanfile.output) == "WARN: Can't install. Please update packages manually or set " \
                                    "'tools.system.package_manager:mode' to 'install'\n"


@pytest.mark.parametrize("tool_class", [Apt, Yum, Dnf, Brew, Pkg, PkgUtil, Chocolatey, PacMan, Zypper])
def test_tools_update_mode_check(tool_class):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = tool_class.tool_name
    conanfile.conf["tools.system.package_manager:mode"] = "check"
    tool = tool_class(conanfile)
    tool.update()
    assert str(conanfile.output) == "WARN: Can't update. Please update packages manually or set " \
                                    "'tools.system.package_manager:mode' to 'install'\n"


@pytest.mark.parametrize("tool_class, result", [
    (Apt, "apt-get update"),
    (Yum, "yum check-update -y"),
    (Dnf, "dnf check-update -y"),
    (Brew, "brew update"),
    (Pkg, "pkg update"),
    (PkgUtil, "pkgutil --catalog"),
    (Chocolatey, "choco outdated"),
    (PacMan, "pacman -Syyu --noconfirm"),
    (Zypper, "zypper --non-interactive ref"),
])
def test_tools_update_mode_install(tool_class, result):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = tool_class.tool_name
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    tool = tool_class(conanfile)
    tool.update()
    assert tool._conanfile.command == result


@pytest.mark.parametrize("tool_class, result", [
    (Apt, 'apt-get install -y --no-install-recommends package1 package2'),
    (Yum, 'yum install -y package1 package2'),
    (Dnf, 'dnf install -y package1 package2'),
    (Brew, 'brew install package1 package2'),
    (Pkg, 'pkg install -y package1 package2'),
    (PkgUtil, 'pkgutil --install --yes package1 package2'),
    (Chocolatey, 'choco --install --yes package1 package2'),
    (PacMan, 'pacman -S --noconfirm package1 package2'),
    (Zypper, 'zypper --non-interactive in package1 package2'),
])
def test_tools_install_mode_install(tool_class, result):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = tool_class.tool_name
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    tool = tool_class(conanfile)
    tool.install(["package1", "package2"])
    assert tool._conanfile.command == result


@pytest.mark.parametrize("tool_class, result", [
    (Apt, 'dpkg-query -W -f=\'${Status}\' package | grep -q "ok installed"'),
    (Yum, 'rpm -q package'),
    (Dnf, 'rpm -q package'),
    (Brew, 'test -n "$(brew ls --versions package)"'),
    (Pkg, 'pkg info package'),
    (PkgUtil, 'test -n "`pkgutil --list package`"'),
    (Chocolatey, 'choco search --local-only --exact package | findstr /c:"1 packages installed."'),
    (PacMan, 'pacman -Qi package'),
    (Zypper, 'rpm -q package'),
])
def test_tools_check(tool_class, result):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = tool_class.tool_name
    tool = tool_class(conanfile)
    tool.check(["package"])
    assert tool._conanfile.command == result


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
                print(not_installed)
        """)})
    client.run("create . test/1.0@ -c tools.system.package_manager:tool=apt-get -s:b arch=armv8 "
               "-s:h arch=x86")
    assert "['non-existing1:i386', 'non-existing2:i386']" in client.out
