import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE


class ExitWithCodeTest(unittest.TestCase):

    def raise_an_error_test(self):

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
        error_code = client.run("build .", ignore_error=True)
        self.assertEquals(error_code, 34)
        self.assertIn("Exiting with code: 34", client.user_io.out)
