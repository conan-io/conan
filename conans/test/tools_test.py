import unittest
from conans.tools import SystemPackageTool, replace_in_file
import os
from conans.test.utils.test_files import temp_folder
from conans import tools
from conans.test.utils.visual_project_files import get_vs_project_files
from conans.test.tools import TestClient
from conans.paths import CONANFILE
import platform


class RunnerMock(object):

    def __init__(self):
        self.command_called = None

    def __call__(self, command, output):
        self.command_called = command


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

    def system_package_tool_test(self):

        runner = RunnerMock()
        spt = SystemPackageTool(runner=runner)

        # fake os info to linux debian, default sudo
        spt._os_info.is_linux = True
        spt._os_info.linux_distro = "debian"
        spt.update()
        self.assertEquals(runner.command_called, "sudo apt-get update")

        spt._os_info.linux_distro = "ubuntu"
        spt.update()
        self.assertEquals(runner.command_called, "sudo apt-get update")

        spt._os_info.linux_distro = "knoppix"
        spt.update()
        self.assertEquals(runner.command_called, "sudo apt-get update")

        spt._os_info.linux_distro = "fedora"
        spt.update()
        self.assertEquals(runner.command_called, "sudo yum check-update")

        spt._os_info.linux_distro = "redhat"
        spt.install("a_package")
        self.assertEquals(runner.command_called, "sudo yum install -y a_package")

        spt._os_info.linux_distro = "debian"
        spt.install("a_package")
        self.assertEquals(runner.command_called, "sudo apt-get install -y a_package")

        spt._os_info.is_macos = True
        spt._os_info.is_linux = False

        spt.update()
        self.assertEquals(runner.command_called, "brew update")
        spt.install("a_package")
        self.assertEquals(runner.command_called, "brew install a_package")

        os.environ["CONAN_SYSREQUIRES_SUDO"] = "False"

        spt = SystemPackageTool(runner=runner)
        spt._os_info.is_linux = True

        spt._os_info.linux_distro = "redhat"
        spt.install("a_package")
        self.assertEquals(runner.command_called, "yum install -y a_package")
        spt.update()
        self.assertEquals(runner.command_called, "yum check-update")

        spt._os_info.linux_distro = "ubuntu"
        spt.install("a_package")
        self.assertEquals(runner.command_called, "apt-get install -y a_package")

        spt.update()
        self.assertEquals(runner.command_called, "apt-get update")

        spt._os_info.is_macos = True
        spt._os_info.is_linux = False

        spt.update()
        self.assertEquals(runner.command_called, "brew update")
        spt.install("a_package")
        self.assertEquals(runner.command_called, "brew install a_package")

        del os.environ["CONAN_SYSREQUIRES_SUDO"]

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
