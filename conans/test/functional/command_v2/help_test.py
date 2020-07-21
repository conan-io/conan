import unittest

from conans.client.tools import environment_append, save, six
from conans.test.utils.tools import TestClient


@unittest.skipIf(six.PY2, "v2.0: Only testing for Python 3")
class CliHelpTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        with environment_append({"CONAN_V2_CLI": "1"}):
            super(CliHelpTest, self).run(*args, **kwargs)

    def help_command_test(self):
        client = TestClient()

        client.run("help")
        self.assertIn("Shows help for a specific command", client.out)

        client.run("help search")
        self.assertIn("Searches for package recipes whose name contain", client.out)

        client.run("--help")
        self.assertIn("Shows help for a specific command", client.out)
