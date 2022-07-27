import platform
from unittest.mock import MagicMock, patch

import mock
import pytest
from mock.mock import PropertyMock

from conan.tools.system.package_manager import Apt, Dnf, Yum, Brew, Pkg, PkgUtil, Chocolatey, Zypper, \
    PacMan, _SystemPackageManagerTool
from conans import Settings
from conans.errors import ConanException
from conans.model.conf import Conf
from conans.test.utils.mocks import ConanFileMock


@pytest.mark.parametrize("platform, tool", [
    ("Linux", "apt-get"),
    ("Windows", "choco"),
    ("Darwin", "brew"),
    ("Solaris", "pkgutil"),
])
@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
def test_package_manager_platform(platform, tool):
    with mock.patch("platform.system", return_value=platform):
        with mock.patch("distro.id", return_value=''):
            with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
                context_mock.return_value = "host"
                conanfile = ConanFileMock()
                conanfile.settings = Settings()
                manager = _SystemPackageManagerTool(conanfile)
                assert tool == manager.get_default_tool()


@pytest.mark.skipif(platform.system() != "Windows", reason="Only Windows")
def test_msys2():
    with mock.patch("platform.system", return_value="Windows"):
        with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
            context_mock.return_value = "host"
            conanfile = ConanFileMock()
            conanfile.conf = Conf()
            conanfile.settings = Settings()
            conanfile.conf["tools.microsoft.bash:subsystem"] = "msys2"
            manager = _SystemPackageManagerTool(conanfile)
            assert manager.get_default_tool() == "pacman"


@pytest.mark.parametrize("distro, tool", [
    ("ubuntu", "apt-get"),
    ("debian", "apt-get"),
    ("pidora", "yum"),
    ("rocky", "yum"),
    ("fedora", "dnf"),
    ("arch", "pacman"),
    ("opensuse", "zypper"),
    ("sles", "zypper"),
    ("opensuse", "zypper"),
    ("opensuse-tumbleweed", "zypper"),
    ("opensuse-leap", "zypper"),
    ("opensuse-next_version", "zypper"),
    ("freebsd", "pkg"),
])
@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
def test_package_manager_distro(distro, tool):
    with mock.patch("platform.system", return_value="Linux"):
        with mock.patch("distro.id", return_value=distro):
            with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
                context_mock.return_value = "host"
                conanfile = ConanFileMock()
                conanfile.settings = Settings()
                manager = _SystemPackageManagerTool(conanfile)
                assert tool == manager.get_default_tool()


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
    with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
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
    with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        apt = Apt(conanfile)
        apt.install(["package1", "package2"], recommends=recommends)
    assert apt._conanfile.command == "apt-get install -y {}package1 package2".format(recommends_str)


@pytest.mark.parametrize("tool_class",
                         [Apt, Yum, Dnf, Brew, Pkg, PkgUtil, Chocolatey, PacMan, Zypper])
def test_tools_install_mode_check(tool_class):
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = tool_class.tool_name
    with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)
        with pytest.raises(ConanException) as exc_info:
            def fake_check(*args, **kwargs):
                return ["package1", "package2"]
            from conan.tools.system.package_manager import _SystemPackageManagerTool
            with patch.object(_SystemPackageManagerTool, 'check', MagicMock(side_effect=fake_check)):
                tool.install(["package1", "package2"])
        assert exc_info.value.args[0] == "System requirements: 'package1, package2' are missing but " \
                                         "can't install because tools.system.package_manager:mode is " \
                                         "'check'.Please update packages manually or set " \
                                         "'tools.system.package_manager:mode' to 'install' in the [conf] " \
                                         "section of the profile, or in the command line using " \
                                         "'-c tools.system.package_manager:mode=install'"


@pytest.mark.parametrize("tool_class, result",
[
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
    for mode in ["check", "install"]:
        conanfile.conf["tools.system.package_manager:mode"] = mode
        with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
            context_mock.return_value = "host"
            tool = tool_class(conanfile)
            tool.update()
            if mode == "install":
                assert tool._conanfile.command == result
            else:
                # does not run the update when mode check
                assert tool._conanfile.command is None


@pytest.mark.parametrize("tool_class, result", [
    (Yum, "yum check-update -y"),
    (Dnf, "dnf check-update -y"),
])
def test_dnf_yum_return_code_100(tool_class, result):
    # https://github.com/conan-io/conan/issues/11661
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.settings = Settings()
    conanfile.conf["tools.system.package_manager:tool"] = tool_class.tool_name
    conanfile.conf["tools.system.package_manager:mode"] = "install"
    with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)

        def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False):
            assert command == result
            return 100 if "check-update" in command else 0

        conanfile.run = fake_run
        tool.update()

    #check that some random return code fails
    with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)

        def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False):
            return 55 if "check-update" in command else 0

        conanfile.run = fake_run
        with pytest.raises(ConanException) as exc_info:
            tool.update()
        assert f"Command '{result}' failed" == str(exc_info.value)


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
    with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)

        def fake_check(*args, **kwargs):
            return ["package1", "package2"]
        from conan.tools.system.package_manager import _SystemPackageManagerTool
        with patch.object(_SystemPackageManagerTool, 'check', MagicMock(side_effect=fake_check)):
            tool.install(["package1", "package2"])


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
    with mock.patch('conans.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)
        tool.check(["package"])
