import unittest
from conans.tools import OSInfo, SystemPackageTool, replace_in_file, AptTool
import os
from conans.test.utils.test_files import temp_folder
from conans import tools
from conans.test.utils.visual_project_files import get_vs_project_files
from conans.test.utils.tools import TestClient, TestBufferConanOutput
from conans.paths import CONANFILE
import platform
from conans.errors import ConanException
from nose.plugins.attrib import attr


class RunnerMock(object):

    def __init__(self, return_ok=True):
        self.command_called = None
        self.return_ok = return_ok

    def __call__(self, command, output):
        self.command_called = command
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

        with open(self.win_file, "rt") as handler:
            content = handler.read()
            self.assertNotIn("nis", content)
            self.assertIn("nus", content)

        with open(self.bytes_file, "rt") as handler:
            content = handler.read()
            self.assertNotIn("nis", content)
            self.assertIn("nus", content)


class ToolsTest(unittest.TestCase):

    def cpu_count_test(self):
        cpus = tools.cpu_count()
        self.assertIsInstance(cpus, int)
        self.assertGreaterEqual(cpus, 1)
        with tools.environment_append({"CONAN_CPU_COUNT": "34"}):
            self.assertEquals(tools.cpu_count(), 34)

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
        runner = RunnerMock(return_ok=False)
        spt = SystemPackageTool(runner=runner)
        if platform.system() == "Linux" or platform.system() == "Darwin":
            msg = "Command 'sudo apt-get update' failed" if platform.system() == "Linux" \
                                                         else "Command 'brew update' failed"
            with self.assertRaisesRegexp(ConanException, msg):
                spt.update()
        else:
            spt.update()  # Won't raise anything because won't do anything

    def system_package_tool_test(self):

        runner = RunnerMock()

        # fake os info to linux debian, default sudo
        os_info = OSInfo()
        os_info.is_linux = True
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
            self.assertEquals(runner.command_called, "sudo apt-get install -y a_package")

        runner.return_ok = True
        spt.install("a_package", force=False)
        self.assertEquals(runner.command_called, "dpkg -s a_package")

        os_info.is_macos = True
        os_info.is_linux = False

        spt = SystemPackageTool(runner=runner, os_info=os_info)
        spt.update()
        self.assertEquals(runner.command_called, "brew update")
        spt.install("a_package", force=True)
        self.assertEquals(runner.command_called, "brew install a_package")

        os.environ["CONAN_SYSREQUIRES_SUDO"] = "False"

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
        self.assertEquals(runner.command_called, "apt-get install -y a_package")

        spt.update()
        self.assertEquals(runner.command_called, "apt-get update")

        os_info.is_macos = True
        os_info.is_linux = False
        spt = SystemPackageTool(runner=runner, os_info=os_info)

        spt.update()
        self.assertEquals(runner.command_called, "brew update")
        spt.install("a_package", force=True)
        self.assertEquals(runner.command_called, "brew install a_package")

        del os.environ["CONAN_SYSREQUIRES_SUDO"]

    def system_package_tool_try_multiple_test(self):
        class RunnerMultipleMock(object):
            def __init__(self, expected=None):
                self.calls = 0
                self.expected = expected

            def __call__(self, command, output):
                self.calls += 1
                return 0 if command in self.expected else 1

        packages = ["a_package", "another_package", "yet_another_package"]

        runner = RunnerMultipleMock(["dpkg -s another_package"])
        spt = SystemPackageTool(runner=runner, tool=AptTool())
        spt.install(packages)
        self.assertEquals(2, runner.calls)

        runner = RunnerMultipleMock(["sudo apt-get update", "sudo apt-get install -y yet_another_package"])
        spt = SystemPackageTool(runner=runner, tool=AptTool())
        spt.install(packages)
        self.assertEquals(7, runner.calls)

        runner = RunnerMultipleMock(["sudo apt-get update"])
        spt = SystemPackageTool(runner=runner, tool=AptTool())
        with self.assertRaises(ConanException):
            spt.install(packages)
        self.assertEquals(7, runner.calls)

    def system_package_tool_installed_test(self):
        if platform.system() != "Linux" and platform.system() != "Macos":
            return
        spt = SystemPackageTool()
        # Git should be installed on development/testing machines
        self.assertTrue(spt._tool.installed("git"))
        # This package hopefully doesn't exist
        self.assertFalse(spt._tool.installed("oidfjgesiouhrgioeurhgielurhgaeiorhgioearhgoaeirhg"))

    @attr('slow')
    def build_vs_project_test(self):
        if platform.system() != "Windows":
            return
        conan_build_vs = """
from conans import ConanFile, tools, ConfigureEnvironment
import platform

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
    exports = "*"
    settings = "os", "build_type", "arch", "compiler"

    def build(self):
        build_command = tools.build_sln_command(self.settings, "MyProject.sln")
        env = ConfigureEnvironment(self)
        command = "%s && %s" % (env.command_line_env, build_command)
        self.output.warn(command)
        self.run(command)

    def package(self):
        self.copy(pattern="*.exe")

"""
        client = TestClient()
        files = get_vs_project_files()
        files[CONANFILE] = conan_build_vs

        # Try with x86_64
        client.save(files)
        client.run("export lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86_64")
        self.assertTrue("Release|x64", client.user_io.out)
        self.assertTrue("Copied 1 '.exe' files: MyProject.exe", client.user_io.out)

        # Try with x86
        client.save(files, clean_first=True)
        client.run("export lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86")
        self.assertTrue("Release|x86", client.user_io.out)
        self.assertTrue("Copied 1 '.exe' files: MyProject.exe", client.user_io.out)

        # Try with x86 debug
        client.save(files, clean_first=True)
        client.run("export lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86 -s build_type=Debug")
        self.assertTrue("Debug|x86", client.user_io.out)
        self.assertTrue("Copied 1 '.exe' files: MyProject.exe", client.user_io.out)

    def download_retries_test(self):
        out = TestBufferConanOutput()

        # Connection error
        with self.assertRaisesRegexp(ConanException, "HTTPConnectionPool"):
            tools.download("http://fakeurl3.es/nonexists",
                           os.path.join(temp_folder(), "file.txt"), out=out,
                           retry=3, retry_wait=0)

        # Not found error
        self.assertEquals(str(out).count("Waiting 0 seconds to retry..."), 2)
        with self.assertRaisesRegexp(ConanException, "Error 404 downloading file"):
            tools.download("https://github.com/conan-io/conan/blob/develop/FILE_NOT_FOUND.txt",
                           os.path.join(temp_folder(), "README.txt"), out=out,
                           retry=3, retry_wait=0)

        # And OK
        dest = os.path.join(temp_folder(), "manual.html")
        tools.download("http://www.zlib.net/manual.html",
                       dest, out=out,
                       retry=3, retry_wait=0)

        self.assertTrue(os.path.exists(dest))
