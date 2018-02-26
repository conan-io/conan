import os
import platform
import unittest

from collections import namedtuple
from six import StringIO

from conans.client.client_cache import CONAN_CONF

from conans import tools
from conans.client.conan_api import ConanAPIV1
from conans.client.conf import default_settings_yml, default_client_conf
from conans.client.output import ConanOutput

from conans.errors import ConanException, NotFoundException
from conans.model.settings import Settings

from conans.test.utils.runner import TestRunner
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestBufferConanOutput

from conans.test.utils.context_manager import which
from conans.tools import OSInfo, SystemPackageTool, replace_in_file, AptTool, ChocolateyTool,\
    set_global_instances
from conans.util.files import save, load
import requests


class RunnerMock(object):
    def __init__(self, return_ok=True):
        self.command_called = None
        self.return_ok = return_ok

    def __call__(self, command, output, win_bash=False, subsystem=None): # @UnusedVariable
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
                update_command = "sudo yum check-update"
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
            self.assertEquals(runner.command_called, "sudo yum check-update")

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
            self.assertEquals(runner.command_called, "dpkg -s a_package")

            
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
                self.assertEquals(runner.command_called, 'choco search --local-only --exact a_package | findstr /c:"1 packages installed."')

        with tools.environment_append({"CONAN_SYSREQUIRES_SUDO": "False"}):

            os_info = OSInfo()
            os_info.is_linux = True
            os_info.linux_distro = "redhat"
            spt = SystemPackageTool(runner=runner, os_info=os_info)
            spt.install("a_package", force=True)
            self.assertEquals(runner.command_called, "yum install -y a_package")
            spt.update()
            self.assertEquals(runner.command_called, "yum check-update")

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
                self.assertEquals(runner.command_called, 'choco search --local-only --exact a_package | findstr /c:"1 packages installed."')

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
            runner = RunnerMultipleMock(["dpkg -s another_package"])
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

            def __call__(self, command, *args, **kwargs):
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

    def msvc_build_command_test(self):
        if platform.system() != "Windows":
            return
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        # test build_type and arch override, for multi-config packages
        cmd = tools.msvc_build_command(settings, "project.sln", build_type="Debug", arch="x86")
        self.assertIn('msbuild project.sln /p:Configuration=Debug /p:Platform="x86"', cmd)
        self.assertIn('vcvarsall.bat', cmd)

        # tests errors if args not defined
        with self.assertRaisesRegexp(ConanException, "Cannot build_sln_command"):
            tools.msvc_build_command(settings, "project.sln")
        settings.arch = "x86"
        with self.assertRaisesRegexp(ConanException, "Cannot build_sln_command"):
            tools.msvc_build_command(settings, "project.sln")

        # succesful definition via settings
        settings.build_type = "Debug"
        cmd = tools.msvc_build_command(settings, "project.sln")
        self.assertIn('msbuild project.sln /p:Configuration=Debug /p:Platform="x86"', cmd)
        self.assertIn('vcvarsall.bat', cmd)

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
            if platform.system() != "Windows":
                self.assertIn("VS non-existing installation", new_out.getvalue())

            with tools.environment_append({"VisualStudioVersion": "12"}):
                with self.assertRaisesRegexp(ConanException,
                                             "Error, Visual environment already set to 12"):
                    tools.vcvars_command(settings)

            with tools.environment_append({"VisualStudioVersion": "12"}):
                # Not raising
                tools.vcvars_command(settings, force=True)

    def run_in_bash_test(self):
        if platform.system() != "Windows":
            return

        class MockConanfile(object):
            def __init__(self):
                self.command = ""
                self.output = namedtuple("output", "info")(lambda x: None)
                self.env = {"PATH": "/path/to/somewhere"}

            def run(self, command, win_bash=False):
                self.command = command

        conanfile = MockConanfile()
        tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin")
        self.assertIn("bash", conanfile.command)
        self.assertIn("--login -c", conanfile.command)
        self.assertIn("^&^& a_command.bat ^", conanfile.command)

        with tools.environment_append({"CONAN_BASH_PATH": "path\\to\\mybash.exe"}):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin")
            self.assertIn('path\\to\\mybash.exe --login -c', conanfile.command)

        with tools.environment_append({"CONAN_BASH_PATH": "path with spaces\\to\\mybash.exe"}):
            tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin")
            self.assertIn('"path with spaces\\to\\mybash.exe" --login -c', conanfile.command)

        # try to append more env vars
        conanfile = MockConanfile()
        tools.run_in_windows_bash(conanfile, "a_command.bat", subsystem="cygwin", env={"PATH": "/other/path",
                                                                                       "MYVAR": "34"})
        self.assertIn('^&^& PATH=\\^"/cygdrive/other/path:/cygdrive/path/to/somewhere:$PATH\\^" '
                      '^&^& MYVAR=34 ^&^& a_command.bat ^', conanfile.command)

    def download_retries_test(self):
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
        tools.download("http://www.zlib.net/manual.html",
                       dest, out=out,
                       retry=3, retry_wait=0)

        self.assertTrue(os.path.exists(dest))
        content = load(dest)

        # overwrite = False
        with self.assertRaises(ConanException):
            tools.download("http://www.zlib.net/manual.html",
                           dest, out=out,
                           retry=3, retry_wait=0, overwrite=False)

        # overwrite = True
        tools.download("http://www.zlib.net/manual.html",
                       dest, out=out,
                       retry=3, retry_wait=0, overwrite=True)

        self.assertTrue(os.path.exists(dest))
        content_new = load(dest)
        self.assertEqual(content, content_new)

        # Not authorized
        with self.assertRaises(ConanException):
            tools.download("https://httpbin.org/basic-auth/user/passwd", dest, overwrite=True)

        # Authorized
        tools.download("https://httpbin.org/basic-auth/user/passwd", dest, auth=("user", "passwd"),
                       overwrite=True)

        # Authorized using headers
        tools.download("https://httpbin.org/basic-auth/user/passwd", dest,
                       headers={"Authorization": "Basic dXNlcjpwYXNzd2Q="}, overwrite=True)
