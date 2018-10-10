# -*- coding: utf-8 -*-
from bottle import static_file, request
import mock
import os
import platform
import unittest
import uuid

from collections import namedtuple

import six
from mock.mock import patch, mock_open
from six import StringIO
from six.moves.urllib.parse import unquote

from conans.client.client_cache import CONAN_CONF

from conans import tools
from conans.client.conan_api import ConanAPIV1
from conans.client.conf import default_settings_yml, default_client_conf
from conans.client.output import ConanOutput
from conans.client.tools.win import vcvars_dict, vswhere
from conans.client.tools.scm import Git, SVN

from conans.errors import ConanException, NotFoundException
from conans.model.build_info import CppInfo
from conans.model.settings import Settings
from conans.test.build_helpers.cmake_test import ConanFileMock

from conans.test.utils.runner import TestRunner
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestBufferConanOutput, create_local_git_repo, \
    SVNLocalRepoTestCase, StoppableThreadBottle

from conans.tools import which
from conans.tools import OSInfo, SystemPackageTool, replace_in_file, AptTool, ChocolateyTool,\
    set_global_instances
from conans.util.files import save, load, md5, mkdir
import requests

from nose.plugins.attrib import attr


class SystemPackageToolTest(unittest.TestCase):
    def setUp(self):
        out = TestBufferConanOutput()
        set_global_instances(out, requests)

    def verify_update_test(self):
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
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, None)
            self.assertIn('Not updating system_requirements. CONAN_SYSREQUIRES_MODE=verify',
                          tools.system_pm._global_output)

    def add_repositories_exception_cases_test(self):
        os_info = OSInfo()
        os_info.is_macos = False
        os_info.is_linux = True
        os_info.is_windows = False
        os_info.linux_distro = "fedora"  # Will instantiate YumTool

        with self.assertRaisesRegexp(ConanException, "add_repository not implemented"):
            spt = SystemPackageTool(os_info=os_info)
            spt.add_repository(repository="deb http://repo/url/ saucy universe multiverse",
                               repo_key=None)

    def add_repository_test(self):
        class RunnerOrderedMock:
            commands = []  # Command + return value

            def __call__(runner_self, command, output, win_bash=False, subsystem=None):
                if not len(runner_self.commands):
                    self.fail("Commands list exhausted, but runner called with '%s'" % command)
                expected, ret = runner_self.commands.pop(0)
                self.assertEqual(expected, command)
                return ret

        def _run_add_repository_test(repository, gpg_key, sudo, update):
            sudo_cmd = "sudo " if sudo else ""
            runner = RunnerOrderedMock()
            runner.commands.append(("{}apt-add-repository {}".format(sudo_cmd, repository), 0))
            if gpg_key:
                runner.commands.append(
                    ("wget -qO - {} | {}apt-key add -".format(gpg_key, sudo_cmd), 0))
            if update:
                runner.commands.append(("{}apt-get update".format(sudo_cmd), 0))

            with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": str(sudo)}):
                os_info = OSInfo()
                os_info.is_macos = False
                os_info.is_linux = True
                os_info.is_windows = False
                os_info.linux_distro = "debian"
                spt = SystemPackageTool(runner=runner, os_info=os_info)

                spt.add_repository(repository=repository, repo_key=gpg_key, update=update)
                self.assertEqual(len(runner.commands), 0)

        # Run several test cases
        repository = "deb http://repo/url/ saucy universe multiverse"
        gpg_key = 'http://one/key.gpg'
        _run_add_repository_test(repository, gpg_key, sudo=True, update=True)
        _run_add_repository_test(repository, gpg_key, sudo=True, update=False)
        _run_add_repository_test(repository, gpg_key, sudo=False, update=True)
        _run_add_repository_test(repository, gpg_key, sudo=False, update=False)
        _run_add_repository_test(repository, gpg_key=None, sudo=True, update=True)
        _run_add_repository_test(repository, gpg_key=None, sudo=False, update=False)

    def system_package_tool_test(self):

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMock()
            # fake os info to linux debian, default sudo
            os_info = OSInfo()
            os_info.is_macos = False
            os_info.is_linux = True
            os_info.is_windows = False
            os_info.linux_distro = "debian"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "sudo apt-get update")

            os_info.linux_distro = "ubuntu"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "sudo apt-get update")

            os_info.linux_distro = "knoppix"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "sudo apt-get update")

            os_info.linux_distro = "fedora"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "sudo yum update")

            os_info.linux_distro = "opensuse"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "sudo zypper --non-interactive ref")

            os_info.linux_distro = "redhat"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.install("a_package", force=False)
            self.assertEquals(runner.command_called, "rpm -q a_package")
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "sudo yum install -y a_package")

            os_info.linux_distro = "debian"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            with self.assertRaises(ConanException):
                runner.return_ok = False
                spt.install("a_package")
                self.assertEquals(runner.command_called, "sudo apt-get install -y --no-install-recommends a_package")

            runner.return_ok = True
            spt.install("a_package", force=False)
            self.assertEquals(runner.command_called, 'dpkg-query -W -f=\'${Status}\' a_package | grep -q "ok installed"')

            os_info.is_macos = True
            os_info.is_linux = False
            os_info.is_windows = False

            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "brew update")
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "brew install a_package")

            os_info.is_freebsd = True
            os_info.is_macos = False

            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "sudo pkg update")
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "sudo pkg install -y a_package")
            spt.install("a_package", force=False)
            self.assertEquals(runner.command_called, "pkg info a_package")

            # Chocolatey is an optional package manager on Windows
            if platform.system() == "Windows" and which("choco.exe"):
                os_info.is_freebsd = False
                os_info.is_windows = True
                spt = SystemPackageTool(runner=runner, os_info=os_info, tool=ChocolateyTool())
                spt.update()
                self.assertEquals(runner.command_called, "choco outdated")
                spt.install("a_package", force=True)
                self.assertEquals(runner.command_called, "choco install --yes a_package")
                spt.install("a_package", force=False)
                self.assertEquals(runner.command_called,
                                  'choco search --local-only --exact a_package | findstr /c:"1 packages installed."')

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "False"}):

            os_info = OSInfo()
            os_info.is_linux = True
            os_info.linux_distro = "redhat"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "yum install -y a_package")
            spt.update()
            self.assertEquals(runner.command_called, "yum update")

            os_info.linux_distro = "ubuntu"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "apt-get install -y --no-install-recommends a_package")

            spt.update()
            self.assertEquals(runner.command_called, "apt-get update")

            os_info.is_macos = True
            os_info.is_linux = False
            os_info.is_windows = False
            spt = SystemPackageTool(runner=runner, os_info=os_info)

            spt.update()
            self.assertEquals(runner.command_called, "brew update")
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "brew install a_package")

            os_info.is_freebsd = True
            os_info.is_macos = False
            os_info.is_windows = False

            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "pkg update")
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "pkg install -y a_package")
            spt.install("a_package", force=False)
            self.assertEquals(runner.command_called, "pkg info a_package")

            os_info.is_solaris = True
            os_info.is_freebsd = False
            os_info.is_windows = False

            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.update()
            self.assertEquals(runner.command_called, "pkgutil --catalog")
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "pkgutil --install --yes a_package")

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):

            # Chocolatey is an optional package manager on Windows
            if platform.system() == "Windows" and which("choco.exe"):
                os_info.is_solaris = False
                os_info.is_windows = True

                spt = SystemPackageTool(runner=runner, os_info=os_info, tool=ChocolateyTool())
                spt.update()
                self.assertEquals(runner.command_called, "choco outdated")
                spt.install("a_package", force=True)
                self.assertEquals(runner.command_called, "choco install --yes a_package")
                spt.install("a_package", force=False)
                self.assertEquals(runner.command_called,
                                  'choco search --local-only --exact a_package | findstr /c:"1 packages installed."')

    def system_package_tool_try_multiple_test(self):
        class RunnerMultipleMock(object):
            def __init__(self, expected=None):
                self.calls = 0
                self.expected = expected

            def __call__(self, command, output):  # @UnusedVariable
                self.calls += 1
                return 0 if command in self.expected else 1

        packages = ["a_package", "another_package", "yet_another_package"]
        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "True"}):
            runner = RunnerMultipleMock(['dpkg-query -W -f=\'${Status}\' another_package | grep -q "ok installed"'])
            spt = SystemPackageTool(runner=runner, tool=AptTool())
            spt.install(packages)
            self.assertEquals(2, runner.calls)
            runner = RunnerMultipleMock(["sudo apt-get update",
                                         "sudo apt-get install -y --no-install-recommends yet_another_package"])
            spt = SystemPackageTool(runner=runner, tool=AptTool())
            spt.install(packages)
            self.assertEquals(7, runner.calls)

            runner = RunnerMultipleMock(["sudo apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool())
            with self.assertRaises(ConanException):
                spt.install(packages)
            self.assertEquals(7, runner.calls)

    def system_package_tool_mode_test(self):
        """
        System Package Tool mode is defined by CONAN_SYSREQUIRES_MODE env variable.
        Allowed values: (enabled, verify, disabled). Parser accepts it in lower/upper case or any combination.
        """

        class RunnerMultipleMock(object):
            def __init__(self, expected=None):
                self.calls = 0
                self.expected = expected

            def __call__(self, command, *args, **kwargs):  # @UnusedVariable
                self.calls += 1
                return 0 if command in self.expected else 1

        packages = ["a_package", "another_package", "yet_another_package"]

        # Check invalid mode raises ConanException
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": "test_not_valid_mode",
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            runner = RunnerMultipleMock([])
            spt = SystemPackageTool(runner=runner, tool=AptTool())
            with self.assertRaises(ConanException) as exc:
                spt.install(packages)
            self.assertIn("CONAN_SYSREQUIRES_MODE=test_not_valid_mode is not allowed", str(exc.exception))
            self.assertEquals(0, runner.calls)

        # Check verify mode, a package report should be displayed in output and ConanException raised.
        # No system packages are installed
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": "VeRiFy",
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            packages = ["verify_package", "verify_another_package", "verify_yet_another_package"]
            runner = RunnerMultipleMock(["sudo apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool())
            with self.assertRaises(ConanException) as exc:
                spt.install(packages)
            self.assertIn("Aborted due to CONAN_SYSREQUIRES_MODE=", str(exc.exception))
            self.assertIn('\n'.join(packages), tools.system_pm._global_output)
            self.assertEquals(3, runner.calls)

        # Check disabled mode, a package report should be displayed in output.
        # No system packages are installed
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": "DiSaBlEd",
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            packages = ["disabled_package", "disabled_another_package", "disabled_yet_another_package"]
            runner = RunnerMultipleMock(["sudo apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool())
            spt.install(packages)
            self.assertIn('\n'.join(packages), tools.system_pm._global_output)
            self.assertEquals(0, runner.calls)

        # Check enabled, default mode, system packages must be installed.
        with tools.environment_append({
            "CONAN_SYSREQUIRES_MODE": "EnAbLeD",
            "CONAN_SYSREQUIRES_SUDO": "True"
        }):
            runner = RunnerMultipleMock(["sudo apt-get update"])
            spt = SystemPackageTool(runner=runner, tool=AptTool())
            with self.assertRaises(ConanException) as exc:
                spt.install(packages)
            self.assertNotIn("CONAN_SYSREQUIRES_MODE", str(exc.exception))
            self.assertEquals(7, runner.calls)

    def system_package_tool_installed_test(self):
        if platform.system() != "Linux" and platform.system() != "Macos" and platform.system() != "Windows":
            return
        if platform.system() == "Windows" and not which("choco.exe"):
            return
        spt = SystemPackageTool()
        expected_package = "git"
        if platform.system() == "Windows" and which("choco.exe"):
            spt = SystemPackageTool(tool=ChocolateyTool())
            # Git is not installed by default on Chocolatey
            expected_package = "chocolatey"
        # The expected should be installed on development/testing machines
        self.assertTrue(spt._tool.installed(expected_package))
        # This package hopefully doesn't exist
        self.assertFalse(spt._tool.installed("oidfjgesiouhrgioeurhgielurhgaeiorhgioearhgoaeirhg"))

    def system_package_tool_fail_when_not_0_returned_test(self):
        def get_linux_error_message():
            """
            Get error message for Linux platform if distro is supported, None otherwise
            """
            os_info = OSInfo()
            update_command = None
            if os_info.with_apt:
                update_command = "sudo apt-get update"
            elif os_info.with_yum:
                update_command = "sudo yum update"
            elif os_info.with_zypper:
                update_command = "sudo zypper --non-interactive ref"
            elif os_info.with_pacman:
                update_command = "sudo pacman -Syyu --noconfirm"

            return "Command '{0}' failed".format(update_command) if update_command is not None else None

        platform_update_error_msg = {
            "Linux": get_linux_error_message(),
            "Darwin": "Command 'brew update' failed",
            "Windows": "Command 'choco outdated' failed" if which("choco.exe") else None,
        }

        runner = RunnerMock(return_ok=False)
        pkg_tool = ChocolateyTool() if which("choco.exe") else None
        spt = SystemPackageTool(runner=runner, tool=pkg_tool)

        msg = platform_update_error_msg.get(platform.system(), None)
        if msg is not None:
            with self.assertRaisesRegexp(ConanException, msg):
                spt.update()
        else:
            spt.update()  # Won't raise anything because won't do anything


class RunnerMock(object):
    def __init__(self, return_ok=True):
        self.command_called = None
        self.return_ok = return_ok

    def __call__(self, command, output, win_bash=False, subsystem=None):  # @UnusedVariable
        self.command_called = command
        self.win_bash = win_bash
        self.subsystem = subsystem
        return 0 if self.return_ok else 1


class ReplaceInFileTest(unittest.TestCase):
    def setUp(self):
        text = u'J\xe2nis\xa7'
        self.tmp_folder = temp_folder()

        self.win_file = os.path.join(self.tmp_folder, "win_encoding.txt")
        text = text.encode("Windows-1252", "ignore")
        with open(self.win_file, "wb") as handler:
            handler.write(text)

        self.bytes_file = os.path.join(self.tmp_folder, "bytes_encoding.txt")
        with open(self.bytes_file, "wb") as handler:
            handler.write(text)

    def test_replace_in_file(self):
        replace_in_file(self.win_file, "nis", "nus")
        replace_in_file(self.bytes_file, "nis", "nus")

        content = tools.load(self.win_file)
        self.assertNotIn("nis", content)
        self.assertIn("nus", content)

        content = tools.load(self.bytes_file)
        self.assertNotIn("nis", content)
        self.assertIn("nus", content)


class ToolsTest(unittest.TestCase):

    def replace_paths_test(self):
        folder = temp_folder()
        path = os.path.join(folder, "file")
        replace_with = "MYPATH"
        expected = 'Some other contentsMYPATH"finally all text'

        save(path, 'Some other contentsc:\\Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/Path/to/file.txt", replace_with, windows_paths=True)
        self.assertEquals(load(path), expected)
        self.assertTrue(ret)

        save(path, 'Some other contentsC:/Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/PATH/to/FILE.txt", replace_with, windows_paths=True)
        self.assertEquals(load(path), expected)
        self.assertTrue(ret)

        save(path, 'Some other contentsD:/Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/PATH/to/FILE.txt", replace_with, strict=False, windows_paths=True)
        self.assertEquals(load(path), 'Some other contentsD:/Path\\TO\\file.txt"finally all text')
        self.assertFalse(ret)

        # Multiple matches
        save(path, 'Some other contentsD:/Path\\TO\\file.txt"finally all textd:\\PATH\\to\\file.TXTMoretext')
        ret = tools.replace_path_in_file(path, "D:/PATH/to/FILE.txt", replace_with, strict=False, windows_paths=True)
        self.assertEquals(load(path), 'Some other contentsMYPATH"finally all textMYPATHMoretext')
        self.assertTrue(ret)

        # Automatic windows_paths
        save(path, 'Some other contentsD:/Path\\TO\\file.txt"finally all textd:\\PATH\\to\\file.TXTMoretext')
        ret = tools.replace_path_in_file(path, "D:/PATH/to/FILE.txt", replace_with, strict=False)
        if platform.system() == "Windows":
            self.assertEquals(load(path), 'Some other contentsMYPATH"finally all textMYPATHMoretext')
            self.assertTrue(ret)
        else:
            self.assertFalse(ret)

    def load_save_test(self):
        folder = temp_folder()
        path = os.path.join(folder, "file")
        save(path, u"äüïöñç")
        content = load(path)
        self.assertEqual(content, u"äüïöñç")

    def md5_test(self):
        result = md5(u"äüïöñç")
        self.assertEqual("dfcc3d74aa447280a7ecfdb98da55174", result)

    def cpu_count_test(self):
        cpus = tools.cpu_count()
        self.assertIsInstance(cpus, int)
        self.assertGreaterEqual(cpus, 1)
        with tools.environment_append({"CONAN_CPU_COUNT": "34"}):
            self.assertEquals(tools.cpu_count(), 34)

    def get_env_unit_test(self):
        """
        Unit tests tools.get_env
        """
        # Test default
        self.assertIsNone(
            tools.get_env("NOT_DEFINED", environment={}),
            None
        )
        # Test defined default
        self.assertEqual(
            tools.get_env("NOT_DEFINED_KEY", default="random_default", environment={}),
            "random_default"
        )
        # Test return defined string
        self.assertEqual(
            tools.get_env("FROM_STR", default="", environment={"FROM_STR": "test_string_value"}),
            "test_string_value"
        )
        # Test boolean conversion
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=False, environment={"BOOL_FROM_STR": "1"}),
            True
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=True, environment={"BOOL_FROM_STR": "0"}),
            False
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=False, environment={"BOOL_FROM_STR": "True"}),
            True
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=True, environment={"BOOL_FROM_STR": ""}),
            False
        )
        # Test int conversion
        self.assertEqual(
            tools.get_env("TO_INT", default=2, environment={"TO_INT": "1"}),
            1
        )
        # Test float conversion
        self.assertEqual(
            tools.get_env("TO_FLOAT", default=2.0, environment={"TO_FLOAT": "1"}),
            1.0
        ),
        # Test list conversion
        self.assertEqual(
            tools.get_env("TO_LIST", default=[], environment={"TO_LIST": "1,2,3"}),
            ["1", "2", "3"]
        )
        self.assertEqual(
            tools.get_env("TO_LIST_NOT_TRIMMED", default=[], environment={"TO_LIST_NOT_TRIMMED": " 1 , 2 , 3 "}),
            ["1", "2", "3"]
        )

    def test_get_env_in_conanfile(self):
        """
        Test get_env is available and working in conanfile
        """
        client = TestClient()

        conanfile = """from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        run_tests = tools.get_env("CONAN_RUN_TESTS", default=False)
        print("test_get_env_in_conafile CONAN_RUN_TESTS=%r" % run_tests)
        assert(run_tests == True)
        """
        client.save({"conanfile.py": conanfile})

        with tools.environment_append({"CONAN_RUN_TESTS": "1"}):
            client.run("install .")
            client.run("build .")

    def test_global_tools_overrided(self):
        client = TestClient()
 
        conanfile = """
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        assert(tools.net._global_requester != None)
        assert(tools.files._global_output != None)
        """
        client.save({"conanfile.py": conanfile})

        client.run("install .")
        client.run("build .")

        # Not test the real commmand get_command if it's setting the module global vars
        tmp = temp_folder()
        conf = default_client_conf.replace("\n[proxies]", "\n[proxies]\nhttp = http://myproxy.com")
        os.mkdir(os.path.join(tmp, ".conan"))
        save(os.path.join(tmp, ".conan", CONAN_CONF), conf)
        with tools.environment_append({"CONAN_USER_HOME": tmp}):
            conan_api, _, _ = ConanAPIV1.factory()
        conan_api.remote_list()
        self.assertEquals(tools.net._global_requester.proxies, {"http": "http://myproxy.com"})
        self.assertIsNotNone(tools.files._global_output.warn)

    def test_environment_nested(self):
        with tools.environment_append({"A": "1", "Z": "40"}):
            with tools.environment_append({"A": "1", "B": "2"}):
                with tools.environment_append({"A": "2", "B": "2"}):
                    self.assertEquals(os.getenv("A"), "2")
                    self.assertEquals(os.getenv("B"), "2")
                    self.assertEquals(os.getenv("Z"), "40")
                self.assertEquals(os.getenv("A", None), "1")
                self.assertEquals(os.getenv("B", None), "2")
            self.assertEquals(os.getenv("A", None), "1")
            self.assertEquals(os.getenv("Z", None), "40")

        self.assertEquals(os.getenv("A", None), None)
        self.assertEquals(os.getenv("B", None), None)
        self.assertEquals(os.getenv("Z", None), None)

    @unittest.skipUnless(platform.system() == "Windows", "Requires vswhere")
    def msvc_build_command_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        # test build_type and arch override, for multi-config packages
        cmd = tools.msvc_build_command(settings, "project.sln", build_type="Debug", arch="x86")
        self.assertIn('msbuild "project.sln" /p:Configuration="Debug" /p:Platform="x86"', cmd)
        self.assertIn('vcvarsall.bat', cmd)

        # tests errors if args not defined
        with self.assertRaisesRegexp(ConanException, "Cannot build_sln_command"):
            tools.msvc_build_command(settings, "project.sln")
        settings.arch = "x86"
        with self.assertRaisesRegexp(ConanException, "Cannot build_sln_command"):
            tools.msvc_build_command(settings, "project.sln")

        # successful definition via settings
        settings.build_type = "Debug"
        cmd = tools.msvc_build_command(settings, "project.sln")
        self.assertIn('msbuild "project.sln" /p:Configuration="Debug" /p:Platform="x86"', cmd)
        self.assertIn('vcvarsall.bat', cmd)

    @unittest.skipUnless(platform.system() == "Windows", "Requires vswhere")
    def vswhere_description_strip_test(self):
        myoutput = """
[
  {
    "instanceId": "17609d7c",
    "installDate": "2018-06-11T02:15:04Z",
    "installationName": "VisualStudio/15.7.3+27703.2026",
    "installationPath": "",
    "installationVersion": "15.7.27703.2026",
    "productId": "Microsoft.VisualStudio.Product.Enterprise",
    "productPath": "",
    "isPrerelease": false,
    "displayName": "Visual Studio Enterprise 2017",
    "description": "生産性向上と、さまざまな規模のチーム間の調整のための Microsoft DevOps ソリューション",
    "channelId": "VisualStudio.15.Release",
    "channelUri": "https://aka.ms/vs/15/release/channel",
    "enginePath": "",
    "releaseNotes": "https://go.microsoft.com/fwlink/?LinkId=660692#15.7.3",
    "thirdPartyNotices": "https://go.microsoft.com/fwlink/?LinkId=660708",
    "updateDate": "2018-06-11T02:15:04.7009868Z",
    "catalog": {
      "buildBranch": "d15.7",
      "buildVersion": "15.7.27703.2026",
      "id": "VisualStudio/15.7.3+27703.2026",
      "localBuild": "build-lab",
      "manifestName": "VisualStudio",
      "manifestType": "installer",
      "productDisplayVersion": "15.7.3",
      "productLine": "Dev15",
      "productLineVersion": "2017",
      "productMilestone": "RTW",
      "productMilestoneIsPreRelease": "False",
      "productName": "Visual Studio",
      "productPatchVersion": "3",
      "productPreReleaseMilestoneSuffix": "1.0",
      "productRelease": "RTW",
      "productSemanticVersion": "15.7.3+27703.2026",
      "requiredEngineVersion": "1.16.1187.57215"
    },
    "properties": {
      "campaignId": "",
      "canceled": "0",
      "channelManifestId": "VisualStudio.15.Release/15.7.3+27703.2026",
      "nickname": "",
      "setupEngineFilePath": ""
    }
  },
  {
    "instanceId": "VisualStudio.12.0",
    "installationPath": "",
    "installationVersion": "12.0"
  }
]

"""
        if six.PY3:
            # In python3 the output from subprocess.check_output are bytes, not str
            myoutput = myoutput.encode()
        myrunner = mock_open()
        myrunner.check_output = lambda x: myoutput
        with patch('conans.client.tools.win.subprocess', myrunner):
            json = vswhere()
            self.assertNotIn("descripton", json)

    def vcvars_echo_test(self):
        if platform.system() != "Windows":
            return
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        cmd = tools.vcvars_command(settings)
        output = TestBufferConanOutput()
        runner = TestRunner(output)
        runner(cmd + " && set vs140comntools")
        self.assertIn("vcvarsall.bat", str(output))
        self.assertIn("VS140COMNTOOLS=", str(output))
        with tools.environment_append({"VisualStudioVersion": "14"}):
            output = TestBufferConanOutput()
            runner = TestRunner(output)
            cmd = tools.vcvars_command(settings)
            runner(cmd + " && set vs140comntools")
            self.assertNotIn("vcvarsall.bat", str(output))
            self.assertIn("Conan:vcvars already set", str(output))
            self.assertIn("VS140COMNTOOLS=", str(output))

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_env_not_duplicated_path_test(self):
        """vcvars is not looking at the current values of the env vars, with PATH it is a problem because you
        can already have set some of the vars and accumulate unnecessary entries."""
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.arch_build = "x86_64"

        # Set the env with a PATH containing the vcvars paths
        tmp = tools.vcvars_dict(settings, only_diff=False)
        tmp = {key.lower(): value for key, value in tmp.items()}
        with tools.environment_append({"path": tmp["path"]}):
            previous_path = os.environ["PATH"].split(";")
            # Duplicate the path, inside the tools.vcvars shouldn't have repeated entries in PATH
            with tools.vcvars(settings):
                path = os.environ["PATH"].split(";")
                values_count = {value: path.count(value) for value in path}
                for value, counter in values_count.items():
                    if value and counter > 1 and previous_path.count(value) != counter:
                        # If the entry was already repeated before calling "tools.vcvars" we keep it
                        self.fail("The key '%s' has been repeated" % value)

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_amd64_32_cross_building_support_test(self):
        # amd64_x86 crossbuilder
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.arch_build = "x86_64"
        cmd = tools.vcvars_command(settings)
        self.assertIn('vcvarsall.bat" amd64_x86', cmd)

        # It follows arch_build first
        settings.arch_build = "x86"
        cmd = tools.vcvars_command(settings)
        self.assertIn('vcvarsall.bat" x86', cmd)

    def vcvars_raises_when_not_found_test(self):
        text = """
os: [Windows]
compiler:
    Visual Studio:
        version: ["5"]
        """
        settings = Settings.loads(text)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "5"
        with self.assertRaisesRegexp(ConanException, "VS non-existing installation: Visual Studio 5"):
            tools.vcvars_command(settings)

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_constrained_test(self):
        text = """os: [Windows]
compiler:
    Visual Studio:
        version: ["14"]
        """
        settings = Settings.loads(text)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        with self.assertRaisesRegexp(ConanException,
                                     "compiler.version setting required for vcvars not defined"):
            tools.vcvars_command(settings)

        new_out = StringIO()
        tools.set_global_instances(ConanOutput(new_out), None)
        settings.compiler.version = "14"
        with tools.environment_append({"vs140comntools": "path/to/fake"}):
            tools.vcvars_command(settings)
            with tools.environment_append({"VisualStudioVersion": "12"}):
                with self.assertRaisesRegexp(ConanException,
                                             "Error, Visual environment already set to 12"):
                    tools.vcvars_command(settings)

            with tools.environment_append({"VisualStudioVersion": "12"}):
                # Not raising
                tools.vcvars_command(settings, force=True)

    def vcvars_context_manager_test(self):
        conanfile = """
from conans import ConanFile, tools

class MyConan(ConanFile):
    name = "MyConan"
    version = "0.1"
    settings = "os", "compiler"

    def build(self):
        with tools.vcvars(self.settings, only_diff=True):
            self.output.info("VCINSTALLDIR set to: " + str(tools.get_env("VCINSTALLDIR")))
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})

        if platform.system() == "Windows":
            client.run("create . conan/testing")
            self.assertNotIn("VCINSTALLDIR set to: None", client.out)
        else:
            client.run("create . conan/testing")
            self.assertIn("VCINSTALLDIR set to: None", client.out)

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def vcvars_dict_diff_test(self):
        text = """
os: [Windows]
compiler:
    Visual Studio:
        version: ["14"]
        """
        settings = Settings.loads(text)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        with tools.environment_append({"MYVAR": "1"}):
            ret = vcvars_dict(settings, only_diff=False)
            self.assertIn("MYVAR", ret)
            self.assertIn("VCINSTALLDIR", ret)

            ret = vcvars_dict(settings)
            self.assertNotIn("MYVAR", ret)
            self.assertIn("VCINSTALLDIR", ret)

        my_lib_paths = "C:\\PATH\TO\MYLIBS;C:\\OTHER_LIBPATH"
        with tools.environment_append({"LIBPATH": my_lib_paths}):
            ret = vcvars_dict(settings, only_diff=False)
            str_var_value = os.pathsep.join(ret["LIBPATH"])
            self.assertTrue(str_var_value.endswith(my_lib_paths))

            # Now only a diff, it should return the values as a list, but without the old values
            ret = vcvars_dict(settings, only_diff=True)
            self.assertEquals(ret["LIBPATH"], str_var_value.split(os.pathsep)[0:-2])

            # But if we apply both environments, they are composed correctly
            with tools.environment_append(ret):
                self.assertEquals(os.environ["LIBPATH"], str_var_value)

    def vcvars_dict_test(self):
        # https://github.com/conan-io/conan/issues/2904
        output_with_newline_and_spaces = """__BEGINS__
     PROCESSOR_ARCHITECTURE=AMD64

PROCESSOR_IDENTIFIER=Intel64 Family 6 Model 158 Stepping 9, GenuineIntel


 PROCESSOR_LEVEL=6 

PROCESSOR_REVISION=9e09    

                         
set nl=^
env_var=
without_equals_sign

ProgramFiles(x86)=C:\Program Files (x86)
       
""".encode("utf-8")

        def vcvars_command_mock(settings, arch, compiler_version, force, vcvars_ver, winsdk_version):  # @UnusedVariable
            return "unused command"

        def subprocess_check_output_mock(cmd, shell):
            self.assertIn("unused command", cmd)
            return output_with_newline_and_spaces

        with mock.patch('conans.client.tools.win.vcvars_command', new=vcvars_command_mock):
            with mock.patch('subprocess.check_output', new=subprocess_check_output_mock):
                vcvars = tools.vcvars_dict(None, only_diff=False)
                self.assertEqual(vcvars["PROCESSOR_ARCHITECTURE"], "AMD64")
                self.assertEqual(vcvars["PROCESSOR_IDENTIFIER"], "Intel64 Family 6 Model 158 Stepping 9, GenuineIntel")
                self.assertEqual(vcvars["PROCESSOR_LEVEL"], "6")
                self.assertEqual(vcvars["PROCESSOR_REVISION"], "9e09")
                self.assertEqual(vcvars["ProgramFiles(x86)"], "C:\Program Files (x86)")

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def run_in_bash_test(self):

        class MockConanfile(object):
            def __init__(self):

                self.output = namedtuple("output", "info")(lambda x: None)  # @UnusedVariable
                self.env = {"PATH": "/path/to/somewhere"}

                class MyRun(object):
                    def __call__(self, command, output, log_filepath=None,
                                 cwd=None, subprocess=False):  # @UnusedVariable
                        self.command = command
                self._conan_runner = MyRun()

        conanfile = MockConanfile()
        with patch.object(OSInfo, "bash_path", return_value='bash'):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin")
            self.assertIn("bash", conanfile._conan_runner.command)
            self.assertIn("--login -c", conanfile._conan_runner.command)
            self.assertIn("^&^& a_command.bat ^", conanfile._conan_runner.command)

        with tools.environment_append({"CONAN_BASH_PATH": "path\\to\\mybash.exe"}):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin")
            self.assertIn('path\\to\\mybash.exe --login -c', conanfile._conan_runner.command)

        with tools.environment_append({"CONAN_BASH_PATH": "path with spaces\\to\\mybash.exe"}):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin")
            self.assertIn('"path with spaces\\to\\mybash.exe" --login -c', conanfile._conan_runner.command)

        # try to append more env vars
        conanfile = MockConanfile()
        with patch.object(OSInfo, "bash_path", return_value='bash'):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin",
                                      env={"PATH": "/other/path", "MYVAR": "34"})
            self.assertIn('^&^& PATH=\\^"/cygdrive/other/path:/cygdrive/path/to/somewhere:$PATH\\^" '
                          '^&^& MYVAR=34 ^&^& a_command.bat ^', conanfile._conan_runner.command)

    def download_retries_test(self):
        http_server = StoppableThreadBottle()

        with tools.chdir(tools.mkdir_tmp()):
            with open("manual.html", "w") as fmanual:
                fmanual.write("this is some content")
                manual_file = os.path.abspath("manual.html")

        from bottle import static_file, auth_basic
        @http_server.server.get("/manual.html")
        def get_manual():
            return static_file(os.path.basename(manual_file),
                               os.path.dirname(manual_file))

        def check_auth(user, password):
            # Check user/password here
            return user == "user" and password == "passwd"

        @http_server.server.get('/basic-auth/<user>/<password>')
        @auth_basic(check_auth)
        def get_manual_auth(user, password):
            return static_file(os.path.basename(manual_file),
                               os.path.dirname(manual_file))

        http_server.run_server()

        out = TestBufferConanOutput()
        set_global_instances(out, requests)
        # Connection error
        with self.assertRaisesRegexp(ConanException, "HTTPConnectionPool"):
            tools.download("http://fakeurl3.es/nonexists",
                           os.path.join(temp_folder(), "file.txt"), out=out,
                           retry=3, retry_wait=0)

        # Not found error
        self.assertEquals(str(out).count("Waiting 0 seconds to retry..."), 2)
        with self.assertRaisesRegexp(NotFoundException, "Not found: "):
            tools.download("https://github.com/conan-io/conan/blob/develop/FILE_NOT_FOUND.txt",
                           os.path.join(temp_folder(), "README.txt"), out=out,
                           retry=3, retry_wait=0)

        # And OK
        dest = os.path.join(temp_folder(), "manual.html")
        tools.download("http://localhost:%s/manual.html" % http_server.port, dest, out=out, retry=3,
                       retry_wait=0)
        self.assertTrue(os.path.exists(dest))
        content = load(dest)

        # overwrite = False
        with self.assertRaises(ConanException):
            tools.download("http://localhost:%s/manual.html" % http_server.port, dest, out=out,
                           retry=3, retry_wait=0, overwrite=False)

        # overwrite = True
        tools.download("http://localhost:%s/manual.html" % http_server.port, dest, out=out, retry=3,
                       retry_wait=0, overwrite=True)
        self.assertTrue(os.path.exists(dest))
        content_new = load(dest)
        self.assertEqual(content, content_new)

        # Not authorized
        with self.assertRaises(ConanException):
            tools.download("http://localhost:%s/basic-auth/user/passwd" % http_server.port, dest,
                           overwrite=True)

        # Authorized
        tools.download("http://localhost:%s/basic-auth/user/passwd" % http_server.port, dest,
                       auth=("user", "passwd"), overwrite=True)

        # Authorized using headers
        tools.download("http://localhost:%s/basic-auth/user/passwd" % http_server.port, dest,
                       headers={"Authorization": "Basic dXNlcjpwYXNzd2Q="}, overwrite=True)
        http_server.stop()

    def get_gnu_triplet_test(self):
        def get_values(this_os, this_arch, setting_os, setting_arch, compiler=None):
            build = tools.get_gnu_triplet(this_os, this_arch, compiler)
            host = tools.get_gnu_triplet(setting_os, setting_arch, compiler)
            return build, host

        build, host = get_values("Linux", "armv6", "Linux", "armv6")
        self.assertEquals(build, "arm-linux-gnueabi")
        self.assertEquals(host, "arm-linux-gnueabi")

        build, host = get_values("Linux", "sparc", "Linux", "sparcv9")
        self.assertEquals(build, "sparc-linux-gnu")
        self.assertEquals(host, "sparc64-linux-gnu")

        build, host = get_values("Linux", "mips", "Linux", "mips64")
        self.assertEquals(build, "mips-linux-gnu")
        self.assertEquals(host, "mips64-linux-gnu")

        build, host = get_values("Linux", "ppc64le", "Linux", "ppc64")
        self.assertEquals(build, "powerpc64le-linux-gnu")
        self.assertEquals(host, "powerpc64-linux-gnu")

        build, host = get_values("Linux", "armv5te", "Linux", "arm_whatever")
        self.assertEquals(build, "arm-linux-gnueabi")
        self.assertEquals(host, "arm-linux-gnueabi")

        build, host = get_values("Linux", "x86_64", "Linux", "armv7hf")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabihf")

        build, host = get_values("Linux", "x86", "Linux", "armv7hf")
        self.assertEquals(build, "x86-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabihf")

        build, host = get_values("Linux", "x86_64", "Linux", "x86")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "x86-linux-gnu")

        build, host = get_values("Linux", "x86_64", "Windows", "x86", compiler="gcc")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "i686-w64-mingw32")

        build, host = get_values("Linux", "x86_64", "Windows", "x86", compiler="Visual Studio")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "i686-windows-msvc")  # Not very common but exists sometimes

        build, host = get_values("Linux", "x86_64", "Linux", "armv7hf")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabihf")

        build, host = get_values("Linux", "x86_64", "Linux", "armv7")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabi")

        build, host = get_values("Linux", "x86_64", "Linux", "armv6")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabi")

        build, host = get_values("Linux", "x86_64", "Android", "x86")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "i686-linux-android")

        build, host = get_values("Linux", "x86_64", "Android", "x86_64")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "x86_64-linux-android")

        build, host = get_values("Linux", "x86_64", "Android", "armv7")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-androideabi")

        build, host = get_values("Linux", "x86_64", "Android", "armv7hf")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-androideabi")

        build, host = get_values("Linux", "x86_64", "Android", "armv8")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "aarch64-linux-android")

        build, host = get_values("Linux", "x86_64", "Android", "armv6")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-androideabi")

        build, host = get_values("Linux", "x86_64", "Windows", "x86", compiler="gcc")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "i686-w64-mingw32")

        build, host = get_values("Linux", "x86_64", "Windows", "x86_64", compiler="gcc")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "x86_64-w64-mingw32")

        build, host = get_values("Windows", "x86_64", "Windows", "x86", compiler="gcc")
        self.assertEquals(build, "x86_64-w64-mingw32")
        self.assertEquals(host, "i686-w64-mingw32")

        build, host = get_values("Windows", "x86_64", "Linux", "armv7hf", compiler="gcc")
        self.assertEquals(build, "x86_64-w64-mingw32")
        self.assertEquals(host, "arm-linux-gnueabihf")

        build, host = get_values("Darwin", "x86_64", "Android", "armv7hf")
        self.assertEquals(build, "x86_64-apple-darwin")
        self.assertEquals(host, "arm-linux-androideabi")

        build, host = get_values("Darwin", "x86_64", "Macos", "x86")
        self.assertEquals(build, "x86_64-apple-darwin")
        self.assertEquals(host, "i686-apple-darwin")

        build, host = get_values("Darwin", "x86_64", "iOS", "armv7")
        self.assertEquals(build, "x86_64-apple-darwin")
        self.assertEquals(host, "arm-apple-darwin")

        build, host = get_values("Darwin", "x86_64", "watchOS", "armv7k")
        self.assertEquals(build, "x86_64-apple-darwin")
        self.assertEquals(host, "arm-apple-darwin")

        build, host = get_values("Darwin", "x86_64", "tvOS", "armv8")
        self.assertEquals(build, "x86_64-apple-darwin")
        self.assertEquals(host, "aarch64-apple-darwin")

        for _os in ["Windows", "Linux"]:
            for arch in ["x86_64", "x86"]:
                triplet = tools.get_gnu_triplet(_os, arch, "gcc")

                output = ""
                if arch == "x86_64":
                    output += "x86_64"
                else:
                    output += "i686" if _os != "Linux" else "x86"

                output += "-"
                if _os == "Windows":
                    output += "w64-mingw32"
                else:
                    output += "linux-gnu"

                self.assertIn(output, triplet)

        # Compiler not specified for os="Windows"
        with self.assertRaises(ConanException):
            tools.get_gnu_triplet("Windows", "x86")

    def detect_windows_subsystem_test(self):
        # Dont raise test
        result = tools.os_info.detect_windows_subsystem()
        if not tools.os_info.bash_path() or platform.system() != "Windows":
            self.assertEqual(None, result)
        else:
            self.assertEqual(str, type(result))

    @attr('slow')
    def get_filename_download_test(self):
        # Create a tar file to be downloaded from server
        with tools.chdir(tools.mkdir_tmp()):
            import tarfile
            tar_file = tarfile.open("sample.tar.gz", "w:gz")
            tools.mkdir("test_folder")
            tar_file.add(os.path.abspath("test_folder"), "test_folder")
            tar_file.close()
            file_path = os.path.abspath("sample.tar.gz")
            assert(os.path.exists(file_path))

        # Instance stoppable thread server and add endpoints
        thread = StoppableThreadBottle()

        @thread.server.get("/this_is_not_the_file_name")
        def get_file():
            return static_file(os.path.basename(file_path), root=os.path.dirname(file_path))

        @thread.server.get("/")
        def get_file2():
            self.assertEquals(request.query["file"], "1")
            return static_file(os.path.basename(file_path), root=os.path.dirname(file_path))

        thread.run_server()

        # Test: File name cannot be deduced from '?file=1'
        with self.assertRaisesRegexp(ConanException,
                                     "Cannot deduce file name form url. Use 'filename' parameter."):
            tools.get("http://localhost:%s/?file=1" % thread.port)

        # Test: Works with filename parameter instead of '?file=1'
        with tools.chdir(tools.mkdir_tmp()):
            tools.get("http://localhost:%s/?file=1" % thread.port, filename="sample.tar.gz")
            self.assertTrue(os.path.exists("test_folder"))

        # Test: Use a different endpoint but still not the filename one
        with tools.chdir(tools.mkdir_tmp()):
            from zipfile import BadZipfile
            with self.assertRaises(BadZipfile):
                tools.get("http://localhost:%s/this_is_not_the_file_name" % thread.port)
            tools.get("http://localhost:%s/this_is_not_the_file_name" % thread.port,
                      filename="sample.tar.gz")
            self.assertTrue(os.path.exists("test_folder"))
        thread.stop()

    def unix_to_dos_unit_test(self):

        def save_file(contents):
            tmp = temp_folder()
            filepath = os.path.join(tmp, "a_file.txt")
            save(filepath, contents)
            return filepath

        fp = save_file(b"a line\notherline\n")
        if not tools.os_info.is_windows:
            import subprocess
            output = subprocess.check_output(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertNotIn("CRLF", str(output))

            tools.unix2dos(fp)
            output = subprocess.check_output(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertIn("CRLF", str(output))
        else:
            fc = tools.load(fp)
            self.assertNotIn("\r\n", fc)
            tools.unix2dos(fp)
            fc = tools.load(fp)
            self.assertIn("\r\n", fc)

        self.assertEquals("a line\r\notherline\r\n", str(tools.load(fp)))

        fp = save_file(b"a line\r\notherline\r\n")
        if not tools.os_info.is_windows:
            import subprocess
            output = subprocess.check_output(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertIn("CRLF", str(output))

            tools.dos2unix(fp)
            output = subprocess.check_output(["file", fp], stderr=subprocess.STDOUT)
            self.assertIn("ASCII text", str(output))
            self.assertNotIn("CRLF", str(output))
        else:
            fc = tools.load(fp)
            self.assertIn("\r\n", fc)
            tools.dos2unix(fp)
            fc = tools.load(fp)
            self.assertNotIn("\r\n", fc)

        self.assertEquals("a line\notherline\n", str(tools.load(fp)))

    def unix_to_dos_conanfile_test(self):
        client = TestClient()
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "file.txt"

    def build(self):
        assert("\\r\\n" in tools.load("file.txt"))
        tools.dos2unix("file.txt")
        assert("\\r\\n" not in tools.load("file.txt"))
        tools.unix2dos("file.txt")
        assert("\\r\\n" in tools.load("file.txt"))
"""
        client.save({"conanfile.py": conanfile, "file.txt": "hello\r\n"})
        client.run("create . user/channel")


class GitToolTest(unittest.TestCase):

    def test_repo_root(self):
        root_path, _ = create_local_git_repo({"myfile": "anything"})

        # Initialized in the root folder
        git = Git(root_path)
        self.assertEqual(root_path, git.get_repo_root())

        # Initialized elsewhere
        subfolder = os.path.join(root_path, 'subfolder')
        os.makedirs(subfolder)
        git = Git(subfolder)
        self.assertEqual(root_path, git.get_repo_root())

    def test_is_pristine(self):
        root_path, _ = create_local_git_repo({"myfile": "anything"})

        git = Git(root_path)
        self.assertTrue(git.is_pristine())

        save(os.path.join(root_path, "other_file"), "content")
        self.assertFalse(git.is_pristine())

        git.run("add .")
        self.assertFalse(git.is_pristine())

        git.run('commit -m "commit"')
        self.assertTrue(git.is_pristine())

    def test_is_local_repository(self):
        root_path, _ = create_local_git_repo({"myfile": "anything"})

        git = Git(temp_folder())
        git.clone(root_path)
        self.assertTrue(git.is_local_repository())
        # TODO: Check that with remote one it is working too

    def test_clone_git(self):
        path, _ = create_local_git_repo({"myfile": "contents"})
        tmp = temp_folder()
        git = Git(tmp)
        git.clone(path)
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))

    def test_clone_existing_folder_git(self):
        path, commit = create_local_git_repo({"myfile": "contents"}, branch="my_release")

        tmp = temp_folder()
        save(os.path.join(tmp, "file"), "dummy contents")
        git = Git(tmp)
        git.clone(path, branch="my_release")
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))

        # Checkout a commit
        git.checkout(commit)
        self.assertEquals(git.get_revision(), commit)

    def test_clone_existing_folder_without_branch(self):
        tmp = temp_folder()
        save(os.path.join(tmp, "file"), "dummy contents")
        git = Git(tmp)
        with self.assertRaisesRegexp(ConanException, "specify a branch to checkout"):
            git.clone("https://github.com/conan-community/conan-zlib.git")

    def test_credentials(self):
        tmp = temp_folder()
        git = Git(tmp, username="peter", password="otool")
        url_credentials = git.get_url_with_credentials("https://some.url.com")
        self.assertEquals(url_credentials, "https://peter:otool@some.url.com")

    def test_verify_ssl(self):
        class MyRunner(object):
            def __init__(self):
                self.calls = []

            def __call__(self, *args, **kwargs):
                self.calls.append(args[0])
                return ""

        runner = MyRunner()
        tmp = temp_folder()
        git = Git(tmp, username="peter", password="otool", verify_ssl=True, runner=runner,
                  force_english=True)
        git.clone(url="https://myrepo.git")
        self.assertIn("git config http.sslVerify true", runner.calls[1])

        runner = MyRunner()
        git = Git(tmp, username="peter", password="otool", verify_ssl=False, runner=runner,
                  force_english=False)
        git.clone(url="https://myrepo.git")
        self.assertIn("git config http.sslVerify false", runner.calls[1])

    def test_clone_submodule_git(self):
        subsubmodule, _ = create_local_git_repo({"subsubmodule": "contents"})
        submodule, _ = create_local_git_repo({"submodule": "contents"}, submodules=[subsubmodule])
        path, commit = create_local_git_repo({"myfile": "contents"}, submodules=[submodule])

        def _create_paths():
            tmp = temp_folder()
            submodule_path = os.path.join(
                tmp,
                os.path.basename(os.path.normpath(submodule)))
            subsubmodule_path = os.path.join(
                submodule_path,
                os.path.basename(os.path.normpath(subsubmodule)))
            return tmp, submodule_path, subsubmodule_path

        # Check old (default) behaviour
        tmp, submodule_path, subsubmodule_path = _create_paths()
        git = Git(tmp)
        git.clone(path)
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))
        self.assertFalse(os.path.exists(os.path.join(submodule_path, "submodule")))

        # Check invalid value
        tmp, submodule_path, subsubmodule_path = _create_paths()
        git = Git(tmp)
        git.clone(path)
        with self.assertRaisesRegexp(ConanException, "Invalid 'submodule' attribute value in the 'scm'."):
            git.checkout(commit, submodule="invalid")

        # Check shallow
        tmp, submodule_path, subsubmodule_path = _create_paths()
        git = Git(tmp)
        git.clone(path)
        git.checkout(commit, submodule="shallow")
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(submodule_path, "submodule")))
        self.assertFalse(os.path.exists(os.path.join(subsubmodule_path, "subsubmodule")))

        # Check recursive
        tmp, submodule_path, subsubmodule_path = _create_paths()
        git = Git(tmp)
        git.clone(path)
        git.checkout(commit, submodule="recursive")
        self.assertTrue(os.path.exists(os.path.join(tmp, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(submodule_path, "submodule")))
        self.assertTrue(os.path.exists(os.path.join(subsubmodule_path, "subsubmodule")))

    def git_to_capture_branch_test(self):
        conanfile = """
import re
from conans import ConanFile, tools

def get_version():
    git = tools.Git()
    try:
        branch = git.get_branch()
        branch = re.sub('[^0-9a-zA-Z]+', '_', branch)
        return "%s_%s" % (branch, git.get_revision())
    except:
        return None

class HelloConan(ConanFile):
    name = "Hello"
    version = get_version()

    def build(self):
        assert("r3le_ase__" in self.version)
        assert(len(self.version) == 50)
"""
        path, _ = create_local_git_repo({"conanfile.py": conanfile}, branch="r3le-ase-")
        client = TestClient()
        client.current_folder = path
        client.run("create . user/channel")

    def git_helper_in_recipe_test(self):
        client = TestClient()
        git_repo = temp_folder()
        save(os.path.join(git_repo, "file.h"), "contents")
        client.runner("git init .", cwd=git_repo)
        client.runner('git config user.email "you@example.com"', cwd=git_repo)
        client.runner('git config user.name "Your Name"', cwd=git_repo)
        client.runner("git checkout -b dev", cwd=git_repo)
        client.runner("git add .", cwd=git_repo)
        client.runner('git commit -m "comm"', cwd=git_repo)

        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "other"

    def source(self):
        git = tools.Git()
        git.clone("%s", "dev")

    def build(self):
        assert(os.path.exists("file.h"))
""" % git_repo.replace("\\", "/")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel")

        # Now clone in a subfolder with later checkout
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "other"

    def source(self):
        tools.mkdir("src")
        git = tools.Git("./src")
        git.clone("%s")
        git.checkout("dev")

    def build(self):
        assert(os.path.exists(os.path.join("src", "file.h")))
""" % git_repo.replace("\\", "/")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel")

        # Base dir, with exports without subfolder and not specifying checkout fails
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "other"

    def source(self):
        git = tools.Git()
        git.clone("%s")

    def build(self):
        assert(os.path.exists("file.h"))
""" % git_repo.replace("\\", "/")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel", ignore_error=True)
        self.assertIn("specify a branch to checkout", client.out)


class SVNToolTestsBasic(SVNLocalRepoTestCase):

    def test_clone(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)
        self.assertTrue(os.path.exists(os.path.join(tmp_folder, 'myfile')))

    def test_revision_number(self):
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        rev = int(svn.get_revision())
        self.create_project(files={'another_file': "content"})
        svn.run("update")
        rev2 = int(svn.get_revision())
        self.assertEqual(rev2, rev + 1)

    def test_repo_url(self):
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        remote_url = svn.get_remote_url()
        self.assertEqual(remote_url.lower(), self.repo_url.lower())

        svn2 = SVN(folder=self.gimme_tmp(create=False))
        svn2.checkout(url=remote_url)  # clone using quoted url
        self.assertEqual(svn2.get_remote_url().lower(), self.repo_url.lower())

    def test_repo_project_url(self):
        project_url, _ = self.create_project(files={"myfile": "content"})
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=project_url)
        self.assertEqual(svn.get_remote_url().lower(), project_url.lower())

    def test_checkout(self):
        # Ensure we have several revisions in the repository
        self.create_project(files={'file': "content"})
        self.create_project(files={'file': "content"})
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        rev = int(svn.get_revision())
        svn.update(revision=rev - 1)  # Checkout previous revision
        self.assertTrue(int(svn.get_revision()), rev-1)

    def test_clone_over_dirty_directory(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)

        new_file = os.path.join(tmp_folder, "new_file")
        with open(new_file, "w") as f:
            f.write("content")

        mod_file = os.path.join(tmp_folder, "myfile")
        with open(mod_file, "a") as f:
            f.write("new content")

        self.assertFalse(svn.is_pristine())
        svn.checkout(url=project_url)  # SVN::clone over a dirty repo reverts all changes (but it doesn't delete non versioned files)
        self.assertTrue(svn.is_pristine())
        # self.assertFalse(os.path.exists(new_file))

    def test_excluded_files(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)

        # Add untracked file
        new_file = os.path.join(tmp_folder, str(uuid.uuid4()))
        with open(new_file, "w") as f:
            f.write("content")

        # Add ignore file
        file_to_ignore = str(uuid.uuid4())
        with open(os.path.join(tmp_folder, file_to_ignore), "w") as f:
            f.write("content")
        svn.run("propset svn:ignore {} .".format(file_to_ignore))
        svn.run('commit -m "add ignored file"')

        excluded_files = svn.excluded_files()
        self.assertIn(file_to_ignore, excluded_files)
        self.assertNotIn('.svn', excluded_files)
        self.assertEqual(len(excluded_files), 1)

    def test_credentials(self):
        svn = SVN(folder=self.gimme_tmp(), username="ada", password="lovelace")
        url_credentials = svn.get_url_with_credentials("https://some.url.com")
        self.assertEquals(url_credentials, "https://ada:lovelace@some.url.com")

    def test_verify_ssl(self):
        class MyRunner(object):
            def __init__(self, svn):
                self.calls = []
                self._runner = svn._runner
                svn._runner = self

            def __call__(self, command, *args, **kwargs):
                self.calls.append(command)
                return self._runner(command, *args, **kwargs)

        project_url, _ = self.create_project(files={'myfile': "contents",
                                                    'subdir/otherfile': "content"})

        svn = SVN(folder=self.gimme_tmp(), username="peter", password="otool", verify_ssl=True)
        runner = MyRunner(svn)
        svn.checkout(url=project_url)
        self.assertNotIn("--trust-server-cert-failures=unknown-ca", runner.calls[1])

        svn = SVN(folder=self.gimme_tmp(), username="peter", password="otool", verify_ssl=False)
        runner = MyRunner(svn)
        svn.checkout(url=project_url)
        if SVN.get_version() >= SVN.API_CHANGE_VERSION:
            self.assertIn("--trust-server-cert-failures=unknown-ca", runner.calls[1])
        else:
            self.assertIn("--trust-server-cert", runner.calls[1])

    def test_repo_root(self):
        project_url, _ = self.create_project(files={'myfile': "contents",
                                                    'subdir/otherfile': "content"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)

        path = os.path.realpath(tmp_folder).replace('\\', '/').lower()
        self.assertEqual(path, svn.get_repo_root().lower())

        # SVN instantiated in a subfolder
        svn2 = SVN(folder=os.path.join(tmp_folder, 'subdir'))
        self.assertFalse(svn2.folder == tmp_folder)
        path = os.path.realpath(tmp_folder).replace('\\', '/').lower()
        self.assertEqual(path, svn2.get_repo_root().lower())

    def test_is_local_repository(self):
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        self.assertTrue(svn.is_local_repository())

        # TODO: Test not local repository

    def test_last_changed_revision(self):
        project_url, _ = self.create_project(files={'project1/myfile': "contents",
                                                    'project2/myfile': "content",
                                                    'project2/subdir1/myfile': "content",
                                                    'project2/subdir2/myfile': "content",
                                                    })
        prj1 = SVN(folder=self.gimme_tmp())
        prj1.checkout(url='/'.join([project_url, 'project1']))

        prj2 = SVN(folder=self.gimme_tmp())
        prj2.checkout(url='/'.join([project_url, 'project2']))

        self.assertEqual(prj1.get_last_changed_revision(), prj2.get_last_changed_revision())

        # Modify file in one subfolder of prj2
        with open(os.path.join(prj2.folder, "subdir1", "myfile"), "a") as f:
            f.write("new content")
        prj2.run('commit -m "add to file"')
        prj2.run('update')
        prj1.run('update')

        self.assertNotEqual(prj1.get_last_changed_revision(), prj2.get_last_changed_revision())
        self.assertEqual(prj1.get_revision(), prj2.get_revision())

        # Instantiate a SVN in the other subfolder
        prj2_subdir2 = SVN(folder=os.path.join(prj2.folder, "subdir2"))
        prj2_subdir2.run('update')
        self.assertEqual(prj2.get_last_changed_revision(),
                         prj2_subdir2.get_last_changed_revision())
        self.assertNotEqual(prj2.get_last_changed_revision(use_wc_root=False),
                            prj2_subdir2.get_last_changed_revision(use_wc_root=False))

    def test_branch(self):
        project_url, _ = self.create_project(files={'prj1/trunk/myfile': "contents",
                                                    'prj1/branches/my_feature/myfile': "",
                                                    'prj1/branches/issue3434/myfile': "",
                                                    'prj1/tags/v12.3.4/myfile': "",
                                                    })
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'trunk']))
        self.assertEqual("trunk", svn.get_branch())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'branches', 'my_feature']))
        self.assertEqual("branches/my_feature", svn.get_branch())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'branches', 'issue3434']))
        self.assertEqual("branches/issue3434", svn.get_branch())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'tags', 'v12.3.4']))
        self.assertEqual("tags/v12.3.4", svn.get_branch())


class SVNToolTestsPristine(SVNLocalRepoTestCase):

    def test_checkout(self):
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        self.assertTrue(svn.is_pristine())

    def test_checkout_project(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})

        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)
        self.assertTrue(svn.is_pristine())

    def test_modified_file(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)
        with open(os.path.join(tmp_folder, "myfile"), "a") as f:
            f.write("new content")
        self.assertFalse(svn.is_pristine())

    def test_untracked_file(self):
        self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=self.repo_url)
        with open(os.path.join(tmp_folder, "not_tracked.txt"), "w") as f:
            f.write("content")
        self.assertTrue(svn.is_pristine())

    def test_ignored_file(self):
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        file_to_ignore = "secret.txt"
        with open(os.path.join(tmp_folder, file_to_ignore), "w") as f:
            f.write("content")
        svn.run("propset svn:ignore {} .".format(file_to_ignore))
        self.assertFalse(svn.is_pristine())  # Folder properties have been modified
        svn.run('commit -m "add ignored file"')
        self.assertTrue(svn.is_pristine())

    def test_conflicted_file(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})

        def work_on_project(tmp_folder):
            svn = SVN(folder=tmp_folder)
            svn.checkout(url=project_url)
            self.assertTrue(svn.is_pristine())
            with open(os.path.join(tmp_folder, "myfile"), "a") as f:
                f.write("random content: {}".format(uuid.uuid4()))
            return svn

        # Two users working on the same project
        svn1 = work_on_project(self.gimme_tmp())
        svn2 = work_on_project(self.gimme_tmp())

        # User1 is faster
        svn1.run('commit -m "user1 commit"')
        self.assertFalse(svn1.is_pristine())
        svn1.run('update')  # Yes, we need to update local copy in order to have the same revision everywhere.
        self.assertTrue(svn1.is_pristine())

        # User2 updates and get a conflicted file
        svn2.run('update')
        self.assertFalse(svn2.is_pristine())
        svn2.run('revert . -R')
        self.assertTrue(svn2.is_pristine())


class SVNToolsTestsRecipe(SVNLocalRepoTestCase):

    conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "other"

    def source(self):
        svn = tools.SVN({svn_folder})
        svn.checkout(url="{svn_url}")

    def build(self):
        assert(os.path.exists("{file_path}"))
        assert(os.path.exists("other"))
"""

    def test_clone_root_folder(self):
        tmp_folder = self.gimme_tmp()
        client = TestClient()
        client.runner('svn co "{}" "{}"'.format(self.repo_url, tmp_folder))
        save(os.path.join(tmp_folder, "file.h"), "contents")
        client.runner("svn add file.h", cwd=tmp_folder)
        client.runner('svn commit -m "message"', cwd=tmp_folder)

        conanfile = self.conanfile.format(svn_folder="", svn_url=self.repo_url,
                                          file_path="file.h")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel")

    def test_clone_subfolder(self):
        tmp_folder = self.gimme_tmp()
        client = TestClient()
        client.runner('svn co "{}" "{}"'.format(self.repo_url, tmp_folder))
        save(os.path.join(tmp_folder, "file.h"), "contents")
        client.runner("svn add file.h", cwd=tmp_folder)
        client.runner('svn commit -m "message"', cwd=tmp_folder)

        conanfile = self.conanfile.format(svn_folder="\"src\"", svn_url=self.repo_url,
                                          file_path="src/file.h")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel")


class CollectLibTestCase(unittest.TestCase):

    def collect_libs_test(self):
        conanfile = ConanFileMock()
        # Without package_folder
        conanfile.package_folder = None
        result = tools.collect_libs(conanfile)
        self.assertEqual([], result)

        # Default behavior
        conanfile.package_folder = temp_folder()
        mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(mylib_path, "")
        conanfile.cpp_info = CppInfo("")
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib"], result)

        # Custom folder
        customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
        save(customlib_path, "")
        result = tools.collect_libs(conanfile, folder="custom_folder")
        self.assertEqual(["customlib"], result)

        # Custom folder doesn't exist
        result = tools.collect_libs(conanfile, folder="fake_folder")
        self.assertEqual([], result)
        self.assertIn("Lib folder doesn't exist, can't collect libraries:", conanfile.output)

        # Use cpp_info.libdirs
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib", "customlib"], result)

        # Custom folder with multiple libdirs should only collect from custom folder
        self.assertEqual(["lib", "custom_folder"], conanfile.cpp_info.libdirs)
        result = tools.collect_libs(conanfile, folder="custom_folder")
        self.assertEqual(["customlib"], result)

        # Warn same lib different folders
        conanfile = ConanFileMock()
        conanfile.package_folder = temp_folder()
        conanfile.cpp_info = CppInfo("")
        custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(custom_mylib_path, "")
        save(lib_mylib_path, "")
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib"], result)
        self.assertIn("Library 'mylib' was either already found in a previous "
                      "'conanfile.cpp_info.libdirs' folder or appears several times with a "
                      "different file extension", conanfile.output)

        # Warn lib folder does not exist with correct result
        conanfile = ConanFileMock()
        conanfile.package_folder = temp_folder()
        conanfile.cpp_info = CppInfo("")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(lib_mylib_path, "")
        no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
        conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
        result = tools.collect_libs(conanfile)
        self.assertEqual(["mylib"], result)
        self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                      % no_folder_path, conanfile.output)

    def self_collect_libs_test(self):
        conanfile = ConanFileMock()
        # Without package_folder
        conanfile.package_folder = None
        result = conanfile.collect_libs()
        self.assertEqual([], result)
        self.assertIn("'self.collect_libs' is deprecated, use 'tools.collect_libs(self)' instead",
                      conanfile.output)

        # Default behavior
        conanfile.package_folder = temp_folder()
        mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(mylib_path, "")
        conanfile.cpp_info = CppInfo("")
        result = conanfile.collect_libs()
        self.assertEqual(["mylib"], result)

        # Custom folder
        customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
        save(customlib_path, "")
        result = conanfile.collect_libs(folder="custom_folder")
        self.assertEqual(["customlib"], result)

        # Custom folder doesn't exist
        result = conanfile.collect_libs(folder="fake_folder")
        self.assertEqual([], result)
        self.assertIn("Lib folder doesn't exist, can't collect libraries:", conanfile.output)

        # Use cpp_info.libdirs
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = conanfile.collect_libs()
        self.assertEqual(["mylib", "customlib"], result)

        # Custom folder with multiple libdirs should only collect from custom folder
        self.assertEqual(["lib", "custom_folder"], conanfile.cpp_info.libdirs)
        result = conanfile.collect_libs(folder="custom_folder")
        self.assertEqual(["customlib"], result)

        # Warn same lib different folders
        conanfile = ConanFileMock()
        conanfile.package_folder = temp_folder()
        conanfile.cpp_info = CppInfo("")
        custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(custom_mylib_path, "")
        save(lib_mylib_path, "")
        conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
        result = conanfile.collect_libs()
        self.assertEqual(["mylib"], result)
        self.assertIn("Library 'mylib' was either already found in a previous "
                      "'conanfile.cpp_info.libdirs' folder or appears several times with a "
                      "different file extension", conanfile.output)

        # Warn lib folder does not exist with correct result
        conanfile = ConanFileMock()
        conanfile.package_folder = temp_folder()
        conanfile.cpp_info = CppInfo("")
        lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
        save(lib_mylib_path, "")
        no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
        conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
        result = conanfile.collect_libs()
        self.assertEqual(["mylib"], result)
        self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                      % no_folder_path, conanfile.output)
