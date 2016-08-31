import unittest
from conans.test.tools import TestClient


class ConanfileExceptionsTest(unittest.TestCase):

    def test_base(self):

        client = TestClient()
        base = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"

    def config(self):
        raise Exception("Something went wrong!")
'''

        files = {"conanfile.py": base}
        client.save(files)
        client.run("export user/channel")
        client.run("install lib/0.1@user/channel", ignore_error=True)
        self.assertIn("ERROR: lib/0.1@user/channel: Error in config, config_options "
                      "or configure() method, line 9",
                      client.user_io.out)
        self.assertIn('raise Exception("Something went wrong!")', client.user_io.out)
