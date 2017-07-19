import unittest
from conans.test.utils.tools import TestBufferConanOutput
from conans.client.detect import detect_defaults_settings
import platform


class DetectTest(unittest.TestCase):

    def detect_test(self):
        output = TestBufferConanOutput()
        result = detect_defaults_settings(output)
        if platform.system() == "Linux":
            for (name, value) in result:
                if name == "compiler":
                    self.assertEquals(value, "gcc")
