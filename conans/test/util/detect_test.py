import platform
import unittest
from subprocess import Popen, PIPE, STDOUT

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
        In some Mac OS X gcc is in reality clang.
        """
        # See: https://github.com/conan-io/conan/issues/2231
        def _execute(command):
            proc = Popen(command, shell=True, bufsize=1, stdout=PIPE, stderr=STDOUT)

            output_buffer = []
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                # output.write(line)
                output_buffer.append(str(line))

            proc.communicate()
            return proc.returncode, "".join(output_buffer)

        proc_return, output = _execute("gcc --version")
        if proc_return != 0 or "clang" not in output:
            # Not test scenario (gcc should display that it's clang)
            return

        output = TestBufferConanOutput()
        with tools.environment_append({"CC": "gcc"}):
            result = detect_defaults_settings(output)
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        self.assertEquals(result.get("compiler", None), "apple-clang")
