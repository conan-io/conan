import unittest
from conans.test.utils.tools import TestClient
from conans import __version__
import sys
from six import StringIO


class BasicClientTest(unittest.TestCase):

    def help_test(self):
        client = TestClient()
        client.run("")
        self.assertIn('Conan commands. Type "conan <command> -h" for help', client.out)

        client.run("--version")
        self.assertIn("Conan version %s" % __version__, client.out)

        error = client.run("some_unknown_command123", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Unknown command 'some_unknown_command123'", client.out)

    def help_cmd_test(self):
        client = TestClient()
        try:
            old_stdout = sys.stdout
            result = StringIO()
            sys.stdout = result
            client.run("help new")
        finally:
            sys.stdout = old_stdout
        self.assertIn("Creates a new package recipe template with a 'conanfile.py'",
                      result.getvalue())

        try:
            old_stdout = sys.stdout
            result = StringIO()
            sys.stdout = result
            client.run("help build")
        finally:
            sys.stdout = old_stdout
        self.assertIn("Calls your local conanfile.py 'build()' method",
                      result.getvalue())

        client.run("help")
        self.assertIn("Creator commands",
                      client.out)

    def help_cmd_error_test(self):
        client = TestClient()
        error = client.run("help not-exists", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Unknown command 'not-exists'", client.out)
