import platform
from unittest.mock import MagicMock, patch

import mock
import pytest
from unittest.mock import PropertyMock

from conan.tools.system.package_manager import Apt, Apk, Dnf, Yum, Brew, Pkg, PkgUtil, Chocolatey, \
    Zypper, PacMan, _SystemPackageManagerTool
from conans.errors import ConanException
from conans.model.settings import Settings
from conan.test.utils.mocks import ConanFileMock, MockSettings


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
            with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
                context_mock.return_value = "host"
                conanfile = ConanFileMock()
                conanfile.settings = Settings()
                manager = _SystemPackageManagerTool(conanfile)
                assert tool == manager.get_default_tool()


@pytest.mark.skipif(platform.system() != "Windows", reason="Only Windows")
def test_msys2():
    with mock.patch("platform.system", return_value="Windows"):
        with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
            context_mock.return_value = "host"
            conanfile = ConanFileMock()
            conanfile.settings = Settings()
            conanfile.conf.define("tools.microsoft.bash:subsystem", "msys2")
            manager = _SystemPackageManagerTool(conanfile)
            assert manager.get_default_tool() == "pacman"


@pytest.mark.parametrize("distro, tool", [
    ("ubuntu", "apt-get"),
    ("debian", "apt-get"),
    ("linuxmint", "apt-get"),
    ("pidora", "yum"),
    ("rocky", "yum"),
    ("fedora", "dnf"),
    ("nobara", "dnf"),
    ("arch", "pacman"),
    ("opensuse", "zypper"),
    ("sles", "zypper"),
    ("opensuse", "zypper"),
    ("opensuse-tumbleweed", "zypper"),
    ("opensuse-leap", "zypper"),
    ("opensuse-next_version", "zypper"),
    ("freebsd", "pkg"),
    ("alpine", "apk"),
    ('altlinux', "apt-get"),
    ("astra", 'apt-get'),
    ('elbrus', 'apt-get'),
    ('pop', "apt-get"),
])
@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
def test_package_manager_distro(distro, tool):
    with mock.patch("platform.system", return_value="Linux"):
        with mock.patch("distro.id", return_value=distro):
            with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
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
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.package_manager:sudo", sudo)
    conanfile.conf.define("tools.system.package_manager:sudo_askpass", sudo_askpass)
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        apt = Apt(conanfile)
    assert apt.sudo_str == expected_str


@pytest.mark.parametrize("recommends, recommends_str", [
    (False, "--no-install-recommends "),
    (True, ""),
])
def test_apt_install_recommends(recommends, recommends_str):
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.package_manager:tool", "apt-get")
    conanfile.conf.define("tools.system.package_manager:mode", "install")
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        apt = Apt(conanfile)
        apt.install(["package1", "package2"], recommends=recommends, check=False)
    assert apt._conanfile.command == "apt-get install -y {}package1 package2".format(recommends_str)


@pytest.mark.parametrize("tool_class",
                         [Apk, Apt, Yum, Dnf, Brew, Pkg, PkgUtil, Chocolatey, PacMan, Zypper])
def test_tools_install_mode_check(tool_class):
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.package_manager:tool", tool_class.tool_name)
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
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
    (Apk, "apk update"),
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
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.package_manager:tool", tool_class.tool_name)
    for mode in ["check", "install"]:
        conanfile.conf.define("tools.system.package_manager:mode", mode)
        with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
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
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.package_manager:tool", tool_class.tool_name)
    conanfile.conf.define("tools.system.package_manager:mode", "install")
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)

        def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False,
                     quiet=False):
            assert command == result
            return 100 if "check-update" in command else 0

        conanfile.run = fake_run
        tool.update()

    # check that some random return code fails
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)

        def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False,
                     quiet=False):
            return 55 if "check-update" in command else 0

        conanfile.run = fake_run
        with pytest.raises(ConanException) as exc_info:
            tool.update()
        assert f"Command '{result}' failed" == str(exc_info.value)


@pytest.mark.parametrize("tool_class, arch_host, result", [
    # Install host package and not cross-compile -> do not add host architecture
    (Apk, 'x86_64', 'apk add --no-cache package1 package2'),
    (Apt, 'x86_64', 'apt-get install -y --no-install-recommends package1 package2'),
    (Yum, 'x86_64', 'yum install -y package1 package2'),
    (Dnf, 'x86_64', 'dnf install -y package1 package2'),
    (Brew, 'x86_64', 'brew install package1 package2'),
    (Pkg, 'x86_64', 'pkg install -y package1 package2'),
    (PkgUtil, 'x86_64', 'pkgutil --install --yes package1 package2'),
    (Chocolatey, 'x86_64', 'choco install --yes package1 package2'),
    (PacMan, 'x86_64', 'pacman -S --noconfirm package1 package2'),
    (Zypper, 'x86_64', 'zypper --non-interactive in package1 package2'),
    # Install host package and cross-compile -> add host architecture
    (Apt, 'x86', 'apt-get install -y --no-install-recommends package1:i386 package2:i386'),
    (Yum, 'x86', 'yum install -y package1.i?86 package2.i?86'),
    (Dnf, 'x86', 'dnf install -y package1.i?86 package2.i?86'),
    (Brew, 'x86', 'brew install package1 package2'),
    (Pkg, 'x86', 'pkg install -y package1 package2'),
    (PkgUtil, 'x86', 'pkgutil --install --yes package1 package2'),
    (Chocolatey, 'x86', 'choco install --yes package1 package2'),
    (PacMan, 'x86', 'pacman -S --noconfirm package1-lib32 package2-lib32'),
    (Zypper, 'x86', 'zypper --non-interactive in package1 package2'),
])
def test_tools_install_mode_install_different_archs(tool_class, arch_host, result):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"arch": arch_host})
    conanfile.settings_build = MockSettings({"arch": "x86_64"})
    conanfile.conf.define("tools.system.package_manager:tool", tool_class.tool_name)
    conanfile.conf.define("tools.system.package_manager:mode", "install")
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)

        def fake_check(*args, **kwargs):
            return ["package1", "package2"]
        from conan.tools.system.package_manager import _SystemPackageManagerTool
        with patch.object(_SystemPackageManagerTool, 'check', MagicMock(side_effect=fake_check)):
            tool.install(["package1", "package2"])

    assert tool._conanfile.command == result

@pytest.mark.parametrize("tool_class, arch_host, result", [
    # Install build machine package and not cross-compile -> do not add host architecture
    (Apk, 'x86_64', 'apk add --no-cache package1 package2'),
    (Apt, 'x86_64', 'apt-get install -y --no-install-recommends package1 package2'),
    (Yum, 'x86_64', 'yum install -y package1 package2'),
    (Dnf, 'x86_64', 'dnf install -y package1 package2'),
    (Brew, 'x86_64', 'brew install package1 package2'),
    (Pkg, 'x86_64', 'pkg install -y package1 package2'),
    (PkgUtil, 'x86_64', 'pkgutil --install --yes package1 package2'),
    (Chocolatey, 'x86_64', 'choco install --yes package1 package2'),
    (PacMan, 'x86_64', 'pacman -S --noconfirm package1 package2'),
    (Zypper, 'x86_64', 'zypper --non-interactive in package1 package2'),
    # Install build machine package and cross-compile -> do not add host architecture
    (Apt, 'x86', 'apt-get install -y --no-install-recommends package1 package2'),
    (Yum, 'x86', 'yum install -y package1 package2'),
    (Dnf, 'x86', 'dnf install -y package1 package2'),
    (Brew, 'x86', 'brew install package1 package2'),
    (Pkg, 'x86', 'pkg install -y package1 package2'),
    (PkgUtil, 'x86', 'pkgutil --install --yes package1 package2'),
    (Chocolatey, 'x86', 'choco install --yes package1 package2'),
    (PacMan, 'x86', 'pacman -S --noconfirm package1 package2'),
    (Zypper, 'x86', 'zypper --non-interactive in package1 package2'),
])
def test_tools_install_mode_install_to_build_machine_arch(tool_class, arch_host, result):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"arch": arch_host})
    conanfile.settings_build = MockSettings({"arch": "x86_64"})
    conanfile.conf.define("tools.system.package_manager:tool", tool_class.tool_name)
    conanfile.conf.define("tools.system.package_manager:mode", "install")
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)

        def fake_check(*args, **kwargs):
            return ["package1", "package2"]
        from conan.tools.system.package_manager import _SystemPackageManagerTool
        with patch.object(_SystemPackageManagerTool, 'check', MagicMock(side_effect=fake_check)):
            tool.install(["package1", "package2"], host_package=False)

    assert tool._conanfile.command == result

@pytest.mark.parametrize("tool_class, result", [
    # cross-compile but arch_names=None -> do not add host architecture
    # https://github.com/conan-io/conan/issues/12320 because the package is archless
    (Apt, 'apt-get install -y --no-install-recommends package1 package2'),
    (Yum, 'yum install -y package1 package2'),
    (Dnf, 'dnf install -y package1 package2'),
    (PacMan, 'pacman -S --noconfirm package1 package2'),
])
def test_tools_install_archless(tool_class, result):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"arch": "x86"})
    conanfile.settings_build = MockSettings({"arch": "x86_64"})
    conanfile.conf.define("tools.system.package_manager:tool", tool_class.tool_name)
    conanfile.conf.define("tools.system.package_manager:mode", "install")
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile, arch_names={})

        def fake_check(*args, **kwargs):
            return ["package1", "package2"]
        from conan.tools.system.package_manager import _SystemPackageManagerTool
        with patch.object(_SystemPackageManagerTool, 'check', MagicMock(side_effect=fake_check)):
            tool.install(["package1", "package2"])

    assert tool._conanfile.command == result


@pytest.mark.parametrize("tool_class, result", [
    (Apk, 'apk info -e package'),
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
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.package_manager:tool", tool_class.tool_name)
    with mock.patch('conan.ConanFile.context', new_callable=PropertyMock) as context_mock:
        context_mock.return_value = "host"
        tool = tool_class(conanfile)
        tool.check(["package"])

    assert tool._conanfile.command == result
