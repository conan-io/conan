import unittest

from conans.test.utils.tools import TestClient


class CliHelpTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        super(CliHelpTest, self).run(*args, **kwargs)

    def test_help_command(self):
        client = TestClient()

        client.run("help")
        self.assertIn("Shows help for a specific command", client.out)

        client.run("help search")
        self.assertIn("Searches for package recipes whose name contain", client.out)
