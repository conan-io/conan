import unittest
from conans.test.utils.tools import TestBufferConanOutput
from conans.client.detect import detect_defaults_settings
import platform


class DetectTest(unittest.TestCase):

    def detect_test(self):
        output = TestBufferConanOutput()
        detect_defaults_settings(output)
        self.assertIn("It seems to be the first time you've ran conan", output)
        if platform.system() == "Linux":
            self.assertIn("Found gcc", output)
