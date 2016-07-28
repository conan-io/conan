
import unittest
from conan.conans.tools import SystemPackageTool
import os


class RunnerMock(object):

    def __init__(self):
        self.command_called = None

    def __call__(self, command, output):
        self.command_called = command


class ToolsTest(unittest.TestCase):

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
