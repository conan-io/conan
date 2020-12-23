import sys
import unittest

import six
import pytest

from conans.test.utils.tools import TestClient


class PythonVersionTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _validate_message(self, expected_message):
        self.client.run("--help")
        self.assertIn(expected_message, str(self.client.out))

    @pytest.mark.skipif(not six.PY2, reason="Requires Python 2.7")
    def test_py2_warning_message(self):
        self._validate_message("Python 2 is deprecated as of 01/01/2020 and Conan has stopped\n"
                               "supporting it officially")

    @pytest.mark.skipif(sys.version_info.major != 3 or sys.version_info.minor != 4, reason="Requires Python 3.4")
    def test_py34_warning_message(self):
        self._validate_message("Python 3.4 support has been dropped. It is strongly "
                               "recommended to use Python >= 3.5 with Conan")
