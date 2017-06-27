import unittest
from conans.test.utils.tools import TestBufferConanOutput
from conans.client.detect import detect_defaults_settings
import platform


class DetectTest(unittest.TestCase):

    def detect_test(self):
        output = TestBufferConanOutput()
        detect_defaults_settings(output, "")
        self.assertIn("Auto detecting your dev setup to initialize the default profile", output)
        if platform.system() == "Linux":
            self.assertIn("Found gcc", output)
