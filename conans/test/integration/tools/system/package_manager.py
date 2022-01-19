import pytest

from conan.tools.system.package_manager import Apt
from conans.model.conf import Conf
from conans.test.utils.mocks import ConanFileMock


@pytest.mark.parametrize("sudo, sudo_askpass, expected_str", [
    (True, True, "sudo -A "),
    (True, False, "sudo "),
    (False, True, ""),
    (False, False, ""),
])
def test_sudo_str(sudo, sudo_askpass, expected_str):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
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
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    apt = Apt(conanfile)
    apt.install(["package1", "package2"], recommends=recommends)
    assert apt._conanfile.command == "apt-get install -y {}package1 package2".format(recommends_str)


def test_apt_install_mode_check():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    apt = Apt(conanfile)
    apt.install(["package1", "package2"])
    assert str(conanfile.output) == "WARN: Can't install. Please update packages manually or set " \
                                    "'tools.system.package_manager:mode' to 'install'\n"


def test_apt_update_mode_check():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    conanfile.conf["tools.system.package_manager:mode"] = "check"
    apt = Apt(conanfile)
    apt.update()
    assert str(conanfile.output) == "WARN: Can't update. Please update packages manually or set " \
                                    "'tools.system.package_manager:mode' to 'install'\n"


def test_apt_update_mode_install():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    apt = Apt(conanfile)
    apt.update()
    assert apt._conanfile.command == "apt-get update"
