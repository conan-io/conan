import mock
import platform
import subprocess
import unittest

from parameterized import parameterized

from conans.client import tools
from conans.client.conf.detect import detect_defaults_settings
from conans.test.utils.tools import TestBufferConanOutput


class DetectTest(unittest.TestCase):

    def detect_default_compilers_test(self):
        platform_default_compilers = {
            "Linux": "gcc",
            "Darwin": "apple-clang",
            "Windows": "Visual Studio"
        }
        output = TestBufferConanOutput()
        result = detect_defaults_settings(output)
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        platform_compiler = platform_default_compilers.get(platform.system(), None)
        if platform_compiler is not None:
            self.assertEqual(result.get("compiler", None), platform_compiler)

    def detect_default_in_mac_os_using_gcc_as_default_test(self):
        """
        Test if gcc in Mac OS X is using apple-clang as frontend
        """
        # See: https://github.com/conan-io/conan/issues/2231
        if platform.system() != "Darwin":
            return

        try:
            output = subprocess.check_output(["gcc", "--version"], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            # gcc is not installed or there is any error (no test scenario)
            return

        if b"clang" not in output:
            # Not test scenario gcc should display clang in output
            # see: https://stackoverflow.com/questions/19535422/os-x-10-9-gcc-links-to-clang
            raise Exception("Apple gcc doesn't point to clang with gcc frontend anymore! please check")

        output = TestBufferConanOutput()
        with tools.environment_append({"CC": "gcc"}):
            result = detect_defaults_settings(output)
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        # No compiler should be detected
        self.assertIsNone(result.get("compiler", None))
        self.assertIn("gcc detected as a frontend using apple-clang", output)
        self.assertIsNotNone(output.error)

    @mock.patch("platform.machine", return_value="")
    def test_detect_empty_arch(self, _):
        result = detect_defaults_settings(output=TestBufferConanOutput())
        result = dict(result)
        self.assertTrue("arch" not in result)
        self.assertTrue("arch_build" not in result)

    @parameterized.expand([
        ['powerpc', '64', '7.1.0.0', 'powerpc'],
        ['powerpc', '32', '7.1.0.0', 'rs6000'],
        ['rs6000', None, '4.2.1.0', 'rs6000']
    ])
    def test_detect_aix(self, processor, bitness, version, expected_arch):
        with mock.patch("platform.machine", mock.MagicMock(return_value='XXXXXXXXXXXX')), \
                mock.patch("platform.processor", mock.MagicMock(return_value=processor)), \
                mock.patch("platform.system", mock.MagicMock(return_value='AIX')), \
                mock.patch("conans.client.tools.oss.OSInfo.getconf", mock.MagicMock(return_value=bitness)), \
                mock.patch('subprocess.check_output', mock.MagicMock(return_value=version)):
            result = detect_defaults_settings(output=TestBufferConanOutput())
            result = dict(result)
            self.assertEqual("AIX", result['os'])
            self.assertEqual("AIX", result['os_build'])
            self.assertEqual(expected_arch, result['arch'])
            self.assertEqual(expected_arch, result['arch_build'])
