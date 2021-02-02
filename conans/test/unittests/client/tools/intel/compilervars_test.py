import mock
import os
import unittest

from conans import Settings
from conans.client.conf import get_default_settings_yml
from conans.client.tools.env import environment_append
from conans.client.tools.intel import intel_compilervars_command
from conans.errors import ConanException
from conans.test.utils.mocks import MockConanfile


class CompilerVarsTest(unittest.TestCase):
    def test_already_set(self):
        with environment_append({"PSTLROOT": "1"}):
            settings = Settings.loads(get_default_settings_yml())
            cvars = intel_compilervars_command(MockConanfile(settings))
            self.assertEqual("echo Conan:intel_compilervars already set", cvars)

    def test_bas_os(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "SunOS"
        with self.assertRaises(ConanException):
            intel_compilervars_command(MockConanfile(settings))

    def test_win(self):
        install_dir = "C:\\Intel"
        with mock.patch("platform.system", mock.MagicMock(return_value="Windows")),\
            mock.patch("conans.client.tools.intel.intel_installation_path",
                       mock.MagicMock(return_value=install_dir)):
            settings = Settings.loads(get_default_settings_yml())
            settings.os = "Windows"
            settings.compiler = "intel"
            settings.compiler.base = "Visual Studio"
            settings.arch = "ppc32"
            with self.assertRaises(ConanException):
                intel_compilervars_command(MockConanfile(settings))

            path = os.path.join(install_dir, "bin", "compilervars.bat")

            settings.arch = "x86"
            cvars = intel_compilervars_command(MockConanfile(settings))
            expected = 'call "%s" -arch ia32' % path
            self.assertEqual(expected, cvars)

            settings.compiler.base.version = "16"
            cvars = intel_compilervars_command(MockConanfile(settings))
            expected = 'call "%s" -arch ia32 vs2019' % path
            self.assertEqual(expected, cvars)

            settings.arch = "x86_64"
            expected = 'call "%s" -arch intel64 vs2019' % path
            cvars = intel_compilervars_command(MockConanfile(settings))
            self.assertEqual(expected, cvars)

    def test_linux(self):
        install_dir = "/opt/intel"
        with mock.patch("platform.system", mock.MagicMock(return_value="Linux")),\
            mock.patch("conans.client.tools.intel.intel_installation_path",
                       mock.MagicMock(return_value="/opt/intel")):
            settings = Settings.loads(get_default_settings_yml())
            settings.os = "Linux"
            settings.compiler = "intel"
            settings.compiler.base = "gcc"
            settings.arch = "ppc32"
            with self.assertRaises(ConanException):
                intel_compilervars_command(MockConanfile(settings))

            path = os.path.join(install_dir, "bin", "compilervars.sh")

            settings.arch = "x86"
            cvars = intel_compilervars_command(MockConanfile(settings))
            expected = 'COMPILERVARS_PLATFORM=linux COMPILERVARS_ARCHITECTURE=ia32 . ' \
                       '"%s" -arch ia32 -platform linux' % path
            self.assertEqual(expected, cvars)

            settings.arch = "x86_64"
            expected = 'COMPILERVARS_PLATFORM=linux COMPILERVARS_ARCHITECTURE=intel64 . ' \
                       '"%s" -arch intel64 -platform linux' % path
            cvars = intel_compilervars_command(MockConanfile(settings))
            self.assertEqual(expected, cvars)

    def test_mac(self):
        install_dir = "/opt/intel"
        with mock.patch("platform.system", mock.MagicMock(return_value="Darwin")),\
            mock.patch("conans.client.tools.intel.intel_installation_path",
                       mock.MagicMock(return_value="/opt/intel")):
            settings = Settings.loads(get_default_settings_yml())
            settings.os = "Macos"
            settings.compiler = "intel"
            settings.compiler.base = "apple-clang"
            settings.arch = "ppc32"
            with self.assertRaises(ConanException):
                intel_compilervars_command(MockConanfile(settings))

            path = os.path.join(install_dir, "bin", "compilervars.sh")

            settings.arch = "x86"
            cvars = intel_compilervars_command(MockConanfile(settings))
            expected = 'COMPILERVARS_PLATFORM=mac COMPILERVARS_ARCHITECTURE=ia32 . ' \
                       '"%s" -arch ia32 -platform mac' % path
            self.assertEqual(expected, cvars)

            settings.arch = "x86_64"
            expected = 'COMPILERVARS_PLATFORM=mac COMPILERVARS_ARCHITECTURE=intel64 . ' \
                       '"%s" -arch intel64 -platform mac' % path
            cvars = intel_compilervars_command(MockConanfile(settings))
            self.assertEqual(expected, cvars)
