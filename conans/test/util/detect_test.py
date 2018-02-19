import platform
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

    @unittest.skipIf(platform.system() != "Darwin", "Test only running in Mac OS X")
    def detect_default_in_mac_os_using_gcc_as_default_test(self):
        # See: https://github.com/conan-io/conan/issues/2231
        output = TestBufferConanOutput()
        with tools.environment_append({"CC": "gcc"}):
            result = detect_defaults_settings(output)
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        self.assertEquals(result.get("compiler", None), "apple-clang")
