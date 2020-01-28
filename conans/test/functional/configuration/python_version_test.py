import sys

import six
import unittest

from conans.test.utils.tools import TestClient


class PythonVersionTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _validate_message(self, expected_message):
        self.client.run("--help")
        self.assertIn(expected_message, str(self.client.out))

    @unittest.skipUnless(six.PY2, "Requires Python 2.7")
    def test_py2_warning_message(self):
        self._validate_message("Python 2 is deprecated as of 01/01/2020 and Conan has stopped\nsupporting it oficially")

    @unittest.skipUnless(sys.version_info.major == 3 and sys.version_info.minor == 4, "Requires Python 3.4")
    def test_py34_warning_message(self):
        self._validate_message("Python 3.4 support has been dropped. It is strongly "
                               "recommended to use Python >= 3.5 with Conan")
