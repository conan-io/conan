import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient


class ExitWithCodeTest(unittest.TestCase):

    def test_raise_an_error(self):

        base = '''
import sys
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello0"
    version = "0.1"

    def build(self):
        sys.exit(34)
'''

        client = TestClient()
        files = {CONANFILE: base}
        client.save(files)
        client.run("install .")
        error_code = client.run("build .", assert_error=True)
        self.assertEqual(error_code, 34)
        self.assertIn("Exiting with code: 34", client.out)
