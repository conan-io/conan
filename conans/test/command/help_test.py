import unittest
from conans.test.utils.tools import TestClient
from conans import __version__


class BasicClientTest(unittest.TestCase):

    def help_test(self):
        client = TestClient()
        client.run("")
        self.assertIn('Conan commands. Type $conan "command" -h', client.out)

        client.run("--version")
        self.assertIn("Conan version %s" % __version__, client.out)

        error = client.run("some_unknown_command123", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Unknown command 'some_unknown_command123'", client.out)
