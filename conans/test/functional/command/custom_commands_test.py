import unittest
import textwrap
import os

from conans.client.tools import environment_append, save
from conans.test.utils.tools import TestClient


class CustomConanCommandsTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        with environment_append({"CONAN_V2_CLI": "1"}):
            super(CustomConanCommandsTest, self).run(*args, **kwargs)

    def setUp(self):
        self._command_file = textwrap.dedent("""
            import argparse
            from conans.cli.command import SmartFormatter, conan_command, OnceArgument

            def output_my_command_cli(message, out):
                out.writeln(message)


            @conan_command(group="My Company commands", cli=output_my_command_cli)
            def {}(*args, conan_api, parser, **kwargs):
                \"""
                Custom command
                \"""
                parser.add_argument('-o', '--output', default="cli", action=OnceArgument,
                                    help="Select the output format: json, html,...")
                args = parser.parse_args(*args)
                message = "Hello custom command!"
                return message, args.output

            """)

    def user_command_add_test(self):
        client = TestClient()
        save(os.path.join(client.cache.cache_folder, "commands", "cmd_my_command.py"),
             self._command_file.format("my_command"))
        client.run("help")
        self.assertIn("My Company commands", client.out)
        self.assertIn("my-command Custom command", client.out)
        client.run("my-command")
        self.assertIn("Hello custom command!", client.out)

    def user_command_no_command_test(self):
        client = TestClient()
        save(os.path.join(client.cache.cache_folder, "commands", "cmd_my_command.py"),
             self._command_file.format("some_name"))
        client.run("help", assert_error=True)
        self.assertIn("ERROR: There is no my_command method defined in cmd_my_command", client.out)
