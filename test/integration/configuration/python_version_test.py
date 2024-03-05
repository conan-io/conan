import sys
import unittest

import pytest

from conans.test.utils.tools import TestClient


class PythonVersionTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _validate_message(self, expected_message):
        self.client.run("--help")
        self.assertIn(expected_message, str(self.client.out))

    @pytest.mark.skipif(sys.version_info.major != 3 or sys.version_info.minor != 4, reason="Requires Python 3.4")
    def test_py34_warning_message(self):
        self._validate_message("Python 3.4 support has been dropped. It is strongly "
                               "recommended to use Python >= 3.5 with Conan")
