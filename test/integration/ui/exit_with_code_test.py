import unittest

from conan.internal.paths import CONANFILE
from conan.test.utils.tools import TestClient
from conans.util.files import save


class ExitWithCodeTest(unittest.TestCase):

    def test_raise_an_error(self):

        base = '''
import sys
from conan import ConanFile

class HelloConan(ConanFile):
    name = "hello0"
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


def test_wrong_home_error():
    client = TestClient()
    save(client.cache.new_config_path, "core.cache:storage_path=//")
    client.run("list *")
    assert "Couldn't initialize storage in" in client.out
