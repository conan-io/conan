import platform
import textwrap

import pytest

from conan.tools.system.package_manager import Apt, Dnf, Yum
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


def test_apt_install_mode_check():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    apt = Apt(conanfile)
    apt.install(["package1", "package2"])
    assert str(conanfile.output) == "WARN: Can't install. Please update packages manually or set " \
                                    "'tools.system.package_manager:mode' to 'install'\n"


def test_apt_update_mode_check():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    conanfile.conf["tools.system.package_manager:mode"] = "check"
    apt = Apt(conanfile)
    apt.update()
    assert str(conanfile.output) == "WARN: Can't update. Please update packages manually or set " \
                                    "'tools.system.package_manager:mode' to 'install'\n"


def test_apt_update_mode_install():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    apt = Apt(conanfile)
    apt.update()
    assert apt._conanfile.command == "apt-get update"


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


def test_yum_update_mode_install():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = "yum"
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    yum = Yum(conanfile)
    yum.update()
    assert yum._conanfile.command == "yum check-update -y"


def test_dnf_update_mode_install():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = "dnf"
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    dnf = Dnf(conanfile)
    dnf.update()
    assert dnf._conanfile.command == "dnf check-update -y"
