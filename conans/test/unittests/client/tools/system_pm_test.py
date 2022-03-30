import mock
import platform
import six
import unittest
from six import StringIO

from conans import tools
from conans.client.output import ConanOutput
from conans.client.tools.files import which
from conans.client.tools.oss import OSInfo
from conans.client.tools.system_pm import ChocolateyTool, SystemPackageTool, AptTool
from conans.errors import ConanException, ConanInvalidSystemRequirements
from conans.test.unittests.util.tools_test import RunnerMock
from conans.test.utils.mocks import MockSettings, MockConanfile, TestBufferConanOutput


class RunnerMultipleMock(object):
    def __init__(self, expected=None):
        self.calls = 0
        self.expected = expected

    def __call__(self, command, *args, **kwargs):  # @UnusedVariable
        self.calls += 1
        return 0 if command in self.expected else 1


class SystemPackageToolTest(unittest.TestCase):
    def setUp(self):
        self.out = TestBufferConanOutput()

    def test_sudo_tty(self):
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "False"}):
            self.assertFalse(SystemPackageTool._is_sudo_enabled())
            self.assertEqual(SystemPackageTool._get_sudo_str(), "")

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            self.assertTrue(SystemPackageTool._is_sudo_enabled())
            self.assertEqual(SystemPackageTool._get_sudo_str(), "sudo -A ")

            with mock.patch("sys.stdout.isatty", return_value=True):
                self.assertEqual(SystemPackageTool._get_sudo_str(), "sudo ")

    def test_system_without_sudo(self):
        with mock.patch("os.path.isfile", return_value=False):
            self.assertFalse(SystemPackageTool._is_sudo_enabled())
            self.assertEqual(SystemPackageTool._get_sudo_str(), "")

            with mock.patch("sys.stdout.isatty", return_value=True):
                self.assertEqual(SystemPackageTool._get_sudo_str(), "")

    def test_verify_update(self):
        # https://github.com/conan-io/conan/issues/3142
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "False",
                                       "CONAN_SYSREQUIRES_MODE": "Verify"}):
            runner = RunnerMock()
            # fake os info to linux debian, default sudo
            os_info = OSInfo()
            os_info.is_macos = False
            os_info.is_linux = True
            os_info.is_windows = False
            os_info.linux_distro = "debian"
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, None)
            self.assertIn('Not updating system_requirements. CONAN_SYSREQUIRES_MODE=verify',
                          self.out)

    # We gotta mock the with_apt property, since it checks for the existence of apt.
    @mock.patch('conans.client.tools.oss.OSInfo.with_apt', new_callable=mock.PropertyMock)
    def test_add_repositories_exception_cases(self, patched_with_apt):
        os_info = OSInfo()
        os_info.is_macos = False
        os_info.is_linux = True
        os_info.is_windows = False
        os_info.linux_distro = "fedora"  # Will instantiate DnfTool

        patched_with_apt.return_value = False

        with six.assertRaisesRegex(self, ConanException, "add_repository not implemented"):
            new_out = StringIO()
            spt = SystemPackageTool(os_info=os_info, output=ConanOutput(new_out))
            spt.add_repository(repository="deb http://repo/url/ saucy universe multiverse",
                               repo_key=None)

    @mock.patch('conans.client.tools.oss.OSInfo.with_apt', new_callable=mock.PropertyMock)
    def test_add_repository(self, patched_with_apt):
        class RunnerOrderedMock:
            commands = []  # Command + return value

            def __call__(runner_self, command, output, win_bash=False, subsystem=None):
                if not len(runner_self.commands):
                    self.fail("Commands list exhausted, but runner called with '%s'" % command)
                expected, ret = runner_self.commands.pop(0)
                self.assertEqual(expected, command)
                return ret

        def _run_add_repository_test(repository, gpg_key, sudo, isatty, update):
            sudo_cmd = ""
            if sudo:
                sudo_cmd = "sudo " if isatty else "sudo -A "

            runner = RunnerOrderedMock()
            if gpg_key:
                runner.commands.append(
                    ("wget -qO - {} | {}apt-key add -".format(gpg_key, sudo_cmd), 0))
            runner.commands.append(("{}apt-add-repository {}".format(sudo_cmd, repository), 0))
            if update:
                runner.commands.append(("{}apt-get update".format(sudo_cmd), 0))

            with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": str(sudo)}):
                os_info = OSInfo()
                os_info.is_macos = False
                os_info.is_linux = True
                os_info.is_windows = False
                os_info.linux_distro = "debian"
                patched_with_apt.return_value = True

                new_out = StringIO()
                spt = SystemPackageTool(runner=runner, os_info=os_info, output=ConanOutput(new_out))

                spt.add_repository(repository=repository, repo_key=gpg_key, update=update)
                self.assertEqual(len(runner.commands), 0)

        # Run several test cases
        repository = "deb http://repo/url/ saucy universe multiverse"
        gpg_key = 'http://one/key.gpg'
        _run_add_repository_test(repository, gpg_key, sudo=True, isatty=False, update=True)
        _run_add_repository_test(repository, gpg_key, sudo=True, isatty=False, update=False)
        _run_add_repository_test(repository, gpg_key, sudo=False, isatty=False, update=True)
        _run_add_repository_test(repository, gpg_key, sudo=False, isatty=False, update=False)
        _run_add_repository_test(repository, gpg_key=None, sudo=True, isatty=False, update=True)
        _run_add_repository_test(repository, gpg_key=None, sudo=False, isatty=True, update=False)

        with mock.patch("sys.stdout.isatty", return_value=True):
            _run_add_repository_test(repository, gpg_key, sudo=True, isatty=True, update=True)

    # We gotta mock the with_apt property, since it checks for the existence of apt.
    @mock.patch('conans.client.tools.oss.OSInfo.with_apt', new_callable=mock.PropertyMock)
    def test_system_package_tool(self, patched_with_apt):

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMock()
            # fake os info to linux debian, default sudo
            os_info = OSInfo()
            os_info.is_macos = False
            os_info.is_linux = True
            os_info.is_windows = False
            patched_with_apt.return_value = True

            os_info.linux_distro = "debian"

            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "sudo -A apt-get update")

            os_info.linux_distro = "ubuntu"
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "sudo -A apt-get update")

            os_info.linux_distro = "knoppix"
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "sudo -A apt-get update")

            os_info.linux_distro = "neon"
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "sudo -A apt-get update")

            # We'll be testing non-Ubuntu and non-Debian-based distros.
            patched_with_apt.return_value = False

            with mock.patch("conans.client.tools.oss.which", return_value=True):
                os_info.linux_distro = "fedora"
                spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
                spt.update()
                self.assertEqual(runner.command_called, "sudo -A dnf check-update -y")

            # Without DNF in the path,
            os_info.linux_distro = "fedora"
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "sudo -A yum check-update -y")

            os_info.linux_distro = "opensuse"
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "sudo -A zypper --non-interactive ref")

            os_info.linux_distro = "redhat"
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.install("a_package", force=False)
            self.assertEqual(runner.command_called, "rpm -q a_package")
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called, "sudo -A yum install -y a_package")

            settings = MockSettings({"arch": "x86", "arch_build": "x86_64", "os": "Linux",
                                     "os_build": "Linux"})
            conanfile = MockConanfile(settings)
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out,
                                    conanfile=conanfile)
            spt.install("a_package", force=False)
            self.assertEqual(runner.command_called, "rpm -q a_package.i?86")
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called, "sudo -A yum install -y a_package.i?86")

            os_info.linux_distro = "debian"
            patched_with_apt.return_value = True
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            with self.assertRaises(ConanException):
                runner.return_ok = False
                spt.install("a_package")
                self.assertEqual(runner.command_called,
                                 "sudo -A apt-get install -y --no-install-recommends a_package")

            runner.return_ok = True
            spt.install("a_package", force=False)
            self.assertEqual(runner.command_called,
                             'dpkg-query -W -f=\'${Status}\' a_package | grep -q "ok installed"')

            os_info.is_macos = True
            os_info.is_linux = False
            os_info.is_windows = False
            patched_with_apt.return_value = False

            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "brew update")
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called, "brew install a_package")

            os_info.is_freebsd = True
            os_info.is_macos = False
            patched_with_apt.return_value = False

            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "sudo -A pkg update")
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called, "sudo -A pkg install -y a_package")
            spt.install("a_package", force=False)
            self.assertEqual(runner.command_called, "pkg info a_package")

            # Chocolatey is an optional package manager on Windows
            if platform.system() == "Windows" and which("choco.exe"):
                os_info.is_freebsd = False
                os_info.is_windows = True
                patched_with_apt.return_value = False
                spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out,
                                        tool=ChocolateyTool(output=self.out))
                spt.update()
                self.assertEqual(runner.command_called, "choco outdated")
                spt.install("a_package", force=True)
                self.assertEqual(runner.command_called, "choco install --yes a_package")
                spt.install("a_package", force=False)
                self.assertEqual(runner.command_called,
                                 'choco search --local-only --exact a_package | '
                                 'findstr /c:"1 packages installed."')

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "False"}):

            os_info = OSInfo()
            os_info.is_linux = True
            os_info.linux_distro = "redhat"
            patched_with_apt.return_value = False

            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called, "yum install -y a_package")
            spt.update()
            self.assertEqual(runner.command_called, "yum check-update -y")

            os_info.linux_distro = "ubuntu"
            patched_with_apt.return_value = True
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called,
                             "apt-get install -y --no-install-recommends a_package")

            spt.update()
            self.assertEqual(runner.command_called, "apt-get update")

            for arch, distro_arch in {"x86_64": "", "x86": ":i386", "ppc32": ":powerpc",
                                      "ppc64le": ":ppc64el", "armv7": ":arm", "armv7hf": ":armhf",
                                      "armv8": ":arm64", "s390x": ":s390x"}.items():
                settings = MockSettings({"arch": arch,
                                         "arch_build": "x86_64",
                                         "os": "Linux",
                                         "os_build": "Linux"})
                conanfile = MockConanfile(settings)
                spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out,
                                        conanfile=conanfile)
                spt.install("a_package", force=True)
                self.assertEqual(runner.command_called,
                            "apt-get install -y --no-install-recommends a_package%s" % distro_arch)

            for arch, distro_arch in {"x86_64": "", "x86": ":all"}.items():
                settings = MockSettings({"arch": arch,
                                         "arch_build": "x86_64",
                                         "os": "Linux",
                                         "os_build": "Linux"})
                conanfile = MockConanfile(settings)
                spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out,
                                        conanfile=conanfile)
                spt.install("a_package", force=True, arch_names={"x86": "all"})
                self.assertEqual(runner.command_called,
                            "apt-get install -y --no-install-recommends a_package%s" % distro_arch)

            os_info.is_macos = True
            os_info.is_linux = False
            os_info.is_windows = False
            patched_with_apt.return_value = False
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)

            spt.update()
            self.assertEqual(runner.command_called, "brew update")
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called, "brew install a_package")

            os_info.is_freebsd = True
            os_info.is_macos = False
            os_info.is_windows = False
            patched_with_apt.return_value = False

            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "pkg update")
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called, "pkg install -y a_package")
            spt.install("a_package", force=False)
            self.assertEqual(runner.command_called, "pkg info a_package")

            os_info.is_solaris = True
            os_info.is_freebsd = False
            os_info.is_windows = False
            patched_with_apt.return_value = False

            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "pkgutil --catalog")
            spt.install("a_package", force=True)
            self.assertEqual(runner.command_called, "pkgutil --install --yes a_package")

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):

            # Chocolatey is an optional package manager on Windows
            if platform.system() == "Windows" and which("choco.exe"):
                os_info.is_solaris = False
                os_info.is_windows = True
                patched_with_apt.return_value = False

                spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out,
                                        tool=ChocolateyTool(output=self.out))
                spt.update()
                self.assertEqual(runner.command_called, "choco outdated")
                spt.install("a_package", force=True)
                self.assertEqual(runner.command_called, "choco install --yes a_package")
                spt.install("a_package", force=False)
                self.assertEqual(runner.command_called,
                                 'choco search --local-only --exact a_package | '
                                 'findstr /c:"1 packages installed."')

    def test_opensuse_zypper_aptitude(self):
        # https://github.com/conan-io/conan/issues/8737
        os_info = OSInfo()
        os_info.is_linux = True
        os_info.is_solaris = False
        os_info.is_macos = False
        os_info.is_windows = False
        os_info.linux_distro = "opensuse"
        runner = RunnerMock()

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "False"}):
            spt = SystemPackageTool(runner=runner, os_info=os_info, output=self.out)
            spt.update()
            self.assertEqual(runner.command_called, "zypper --non-interactive ref")

    def test_system_package_tool_try_multiple(self):
        packages = ["a_package", "another_package", "yet_another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(['dpkg-query -W -f=\'${Status}\' another_package | '
                                         'grep -q "ok installed"'])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install(packages)
            self.assertEqual(2, runner.calls)
            runner = RunnerMultipleMock(["sudo -A apt-get update",
                                         "sudo -A apt-get install -y --no-install-recommends"
                                         " yet_another_package"])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install(packages)
            self.assertEqual(7, runner.calls)

            runner = RunnerMultipleMock(["sudo -A apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            with self.assertRaises(ConanException):
                spt.install(packages)
            self.assertEqual(7, runner.calls)

    def test_system_package_tool_mode(self):
        """
        System Package Tool mode is defined by CONAN_SYSREQUIRES_MODE env variable.
        Allowed values: (enabled, verify, disabled). Parser accepts it in lower/upper
        case or any combination.
        """
        packages = ["a_package", "another_package", "yet_another_package"]

        # Check invalid mode raises ConanException
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": "test_not_valid_mode",
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            runner = RunnerMultipleMock([])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            with self.assertRaises(ConanException) as exc:
                spt.install(packages)
            self.assertIn("CONAN_SYSREQUIRES_MODE=test_not_valid_mode is not allowed",
                          str(exc.exception))
            self.assertEqual(0, runner.calls)

        # Check verify mode, a package report should be shown in output and ConanException raised.
        # No system packages are installed
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": "VeRiFy",
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            packages = ["verify_package", "verify_another_package", "verify_yet_another_package"]
            runner = RunnerMultipleMock(["sudo -A apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            with self.assertRaises(ConanInvalidSystemRequirements) as exc:
                spt.install(packages)
            self.assertIn("Aborted due to CONAN_SYSREQUIRES_MODE=", str(exc.exception))
            self.assertIn('\n'.join(packages), self.out)
            self.assertEqual(3, runner.calls)

        # Check disabled mode, a package report should be displayed in output.
        # No system packages are installed
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": "DiSaBlEd",
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            packages = ["disabled_package", "disabled_another_package",
                        "disabled_yet_another_package"]
            runner = RunnerMultipleMock(["sudo -A apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install(packages)
            self.assertIn('\n'.join(packages), self.out)
            self.assertEqual(0, runner.calls)

        # Check enabled, default mode, system packages must be installed.
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": "EnAbLeD",
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            runner = RunnerMultipleMock(["sudo -A apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            with self.assertRaises(ConanException) as exc:
                spt.install(packages)
            self.assertNotIn("CONAN_SYSREQUIRES_MODE", str(exc.exception))
            self.assertEqual(7, runner.calls)

        # Check default_mode. The environment variable is not set and should behave like
        # the default_mode
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": None,
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            packages = ["verify_package", "verify_another_package", "verify_yet_another_package"]
            runner = RunnerMultipleMock(["sudo -A apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out,
                                    default_mode="verify")
            with self.assertRaises(ConanInvalidSystemRequirements) as exc:
                spt.install(packages)
            self.assertIn("Aborted due to CONAN_SYSREQUIRES_MODE=", str(exc.exception))
            self.assertIn('\n'.join(packages), self.out)
            self.assertEqual(3, runner.calls)

    def test_system_package_tool_installed(self):
        if (platform.system() != "Linux" and platform.system() != "Macos" and
                platform.system() != "Windows"):
            return
        if platform.system() == "Windows" and not which("choco.exe"):
            return
        spt = SystemPackageTool(output=self.out)
        expected_package = "git"
        if platform.system() == "Windows" and which("choco.exe"):
            spt = SystemPackageTool(tool=ChocolateyTool(output=self.out), output=self.out)
            # Git is not installed by default on Chocolatey
            expected_package = "chocolatey"
        else:
            if platform.system() != "Windows" and not which("git"):
                return
        # The expected should be installed on development/testing machines
        self.assertTrue(spt._tool.installed(expected_package))
        self.assertTrue(spt.installed(expected_package))
        # This package hopefully doesn't exist
        self.assertFalse(spt._tool.installed("oidfjgesiouhrgioeurhgielurhgaeiorhgioearhgoaeirhg"))
        self.assertFalse(spt.installed("oidfjgesiouhrgioeurhgielurhgaeiorhgioearhgoaeirhg"))

    def test_system_package_tool_fail_when_not_0_returned(self):
        def get_linux_error_message():
            """
            Get error message for Linux platform if distro is supported, None otherwise
            """
            os_info = OSInfo()
            update_command = None
            if os_info.with_apt:
                update_command = "sudo -A apt-get update"
            elif os_info.with_yum:
                update_command = "sudo -A yum check-update -y"
            elif os_info.with_dnf:
                update_command = "sudo -A dnf check-update -y"
            elif os_info.with_zypper:
                update_command = "sudo -A zypper --non-interactive ref"
            elif os_info.with_pacman:
                update_command = "sudo -A pacman -Syyu --noconfirm"

            return ("Command '{0}' failed".format(update_command)
                    if update_command is not None else None)

        platform_update_error_msg = {
            "Linux": get_linux_error_message(),
            "Darwin": "Command 'brew update' failed",
            "Windows": "Command 'choco outdated' failed" if which("choco.exe") else None,
        }

        runner = RunnerMock(return_ok=False)
        output = ConanOutput(StringIO())
        pkg_tool = ChocolateyTool(output=output) if which("choco.exe") else None
        spt = SystemPackageTool(runner=runner, tool=pkg_tool, output=output)

        msg = platform_update_error_msg.get(platform.system(), None)
        if msg is not None:
            with six.assertRaisesRegex(self, ConanException, msg):
                spt.update()
        else:
            spt.update()  # Won't raise anything because won't do anything

    def test_install_all_packages(self):
        """ SystemPackageTool must install all packages
        """
        # No packages installed
        packages = ["a_package", "another_package", "yet_another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(["sudo -A apt-get update",
                                         "sudo -A apt-get install -y --no-install-recommends"
                                         " a_package another_package yet_another_package",
                                         ])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install_packages(packages)
            self.assertEqual(5, runner.calls)

    def test_install_few_packages(self):
        """ SystemPackageTool must install 2 packages only
        """
        packages = ["a_package", "another_package", "yet_another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(['dpkg-query -W -f=\'${Status}\' a_package | '
                                         'grep -q "ok installed"',
                                         "sudo -A apt-get update",
                                         "sudo -A apt-get install -y --no-install-recommends"
                                         " another_package yet_another_package",
                                         ])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install_packages(packages)
            self.assertEqual(5, runner.calls)

    def test_packages_installed(self):
        """ SystemPackageTool must not install. All packages are installed.
        """
        packages = ["a_package", "another_package", "yet_another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(['dpkg-query -W -f=\'${Status}\' a_package | '
                                         'grep -q "ok installed"',
                                         'dpkg-query -W -f=\'${Status}\' another_package | '
                                         'grep -q "ok installed"',
                                         'dpkg-query -W -f=\'${Status}\' yet_another_package | '
                                         'grep -q "ok installed"',
                                         ])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install_packages(packages)
            self.assertEqual(3, runner.calls)

    def test_empty_package_list(self):
        """ Install nothing
        """
        packages = []
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock()
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out),
                                    output=self.out)
            spt.install_packages(packages)
            self.assertEqual(0, runner.calls)

    def test_install_variants_and_packages(self):
        """ SystemPackageTool must install one of variants and all packages at same list
        """
        packages = [("varianta", "variantb", "variantc"), "a_package", "another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(["sudo -A apt-get update",
                                         "sudo -A apt-get install -y --no-install-recommends"
                                         " varianta",
                                         "sudo -A apt-get update",
                                         "sudo -A apt-get install -y --no-install-recommends"
                                         " a_package another_package",
                                         ])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install_packages(packages)
            self.assertEqual(8, runner.calls)

    def test_installed_variant_and_install_packages(self):
        """ Only packages must be installed. Variants are already installed
        """
        packages = [("varianta", "variantb", "variantc"), "a_package", "another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(['dpkg-query -W -f=\'${Status}\' varianta | '
                                         'grep -q "ok installed"',
                                         "sudo -A apt-get update",
                                         "sudo -A apt-get install -y --no-install-recommends"
                                         " a_package another_package",
                                         ])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install_packages(packages)
            self.assertEqual(5, runner.calls)

    def test_installed_packages_and_install_variant(self):
        """ Only variant must be installed. Packages are already installed
        """
        packages = [("varianta", "variantb", "variantc"), "a_package", "another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(['dpkg-query -W -f=\'${Status}\' a_package | '
                                         'grep -q "ok installed"',
                                         'dpkg-query -W -f=\'${Status}\' another_package | '
                                         'grep -q "ok installed"',
                                         "sudo -A apt-get update",
                                         "sudo -A apt-get install -y --no-install-recommends"
                                         " varianta",
                                         ])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install_packages(packages)
            self.assertEqual(7, runner.calls)

    def test_variants_and_packages_installed(self):
        """ Install nothing, all is already installed
        """
        packages = [("varianta", "variantb", "variantc"), "a_package", "another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(['dpkg-query -W -f=\'${Status}\' varianta | '
                                         'grep -q "ok installed"',
                                         'dpkg-query -W -f=\'${Status}\' a_package | '
                                         'grep -q "ok installed"',
                                         'dpkg-query -W -f=\'${Status}\' another_package | '
                                         'grep -q "ok installed"',
                                         ])
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
            spt.install_packages(packages)
            self.assertEqual(3, runner.calls)

    def test_empty_variants_and_packages(self):
        packages = [(),]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock()
            spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out),
                                    output=self.out)
            spt.install_packages(packages)
            self.assertEqual(0, runner.calls)

    def test_install_all_multiple_package_list(self):
        """ Separated string list must be treated as full package list to be installed
        """
        packages = "varianta variantb", "variantc variantd"
        runner = RunnerMultipleMock([])
        spt = SystemPackageTool(runner=runner, tool=AptTool(output=self.out), output=self.out)
        with self.assertRaises(ConanException) as error:
            spt.install_packages(packages)
            self.assertEqual("Each string must contain only one package to be installed."
                             " Use a list instead e.g. ['foo', 'bar'].", str(error.exception))
