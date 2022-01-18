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
def test_apt_install(recommends, recommends_str):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    apt = Apt(conanfile)
    apt.install(["package1", "package2"], recommends=recommends)
    assert apt._conanfile.command == "apt-get install -y {}package1 package2".format(recommends_str)


def test_apt_update():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    apt = Apt(conanfile)
    apt.update()
    assert apt._conanfile.command == "apt-get update"


def test_apt_update_check_mode():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf["tools.system.package_manager:tool"] = "apt-get"
    apt = Apt(conanfile)
    apt.update()
    assert apt._conanfile.command == "apt-get update"
