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
        self._validate_message("Python 2 will soon be deprecated. It is strongly " \
                               "recommended to use Python >= 3.5 with Conan")

    @unittest.skipUnless(six.PY34, "Requires Python 3.4")
    def test_py34_warning_message(self):
        self._validate_message("Python 3.4 support has been dropped. It is strongly " \
                               "recommended to use Python >= 3.5 with Conan")
