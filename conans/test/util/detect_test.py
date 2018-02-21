import platform
import subprocess
import unittest

from conans import tools
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
            self.assertEquals(result.get("compiler", None), platform_compiler)

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

        if "clang" not in output:
            # Not test scenario gcc should display clang in output
            return

        output = TestBufferConanOutput()
        with tools.environment_append({"CC": "gcc"}):
            result = detect_defaults_settings(output)
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        self.assertEquals(result.get("compiler", None), "apple-clang")
        self.assertIn("gcc detected as a frontend using apple-clang", output)
        self.assertIsNotNone(output.warn)
