import sys
import unittest
import textwrap
import os

from conans.client.tools import environment_append, save
from conans.test.utils.tools import TestClient


class CliHelpTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        with environment_append({"CONAN_V2_CLI": "1"}):
            super(CliHelpTest, self).run(*args, **kwargs)

    def help_command_test(self):
        client = TestClient()

        client.run("help")
        self.assertIn('Shows help for a specific command', client.out)

        client.run("help search")
        self.assertIn('Searches for package recipes whose name contain', client.out)

        client.run("--help")
        self.assertIn('Shows help for a specific command', client.out)

        client.run("search --help")
        print(client.out)
        self.assertIn('Searches for package recipes whose name contain', client.out)
