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


            @conan_command(group="My Company commands")
            def {}(conan_api, parser, *args, **kwargs):
                \"""
                Custom command
                \"""
                conan_api = kwargs["conan_api"]
                parser = kwargs["parser"]
                parser.add_argument('-o', '--output', default="cli", action=OnceArgument,
                                    help="Select the output format: json, html,...")
                args = parser.parse_args(*args)
                message = "Hello custom command!"
                MyCommandFormatter.out(args.output, message, conan_api.out)


            class MyCommandFormatter(BaseFormatter):

                @classmethod
                def cli(cls, message, out):
                    out.writeln(message)
            """)

    def user_command_add_test(self):
        client = TestClient()
        save(os.path.join(client.cache.cache_folder, "commands", "cmd_my_command.py"),
             self._command_file.format("my_command"))
        save(os.path.join(client.cache.cache_folder, "commands", "my_command_formatter.py"),
             self._formatter_file)
        client.run("help")
        self.assertIn("My Company commands", client.out)
        self.assertIn("my-command Custom command", client.out)
        client.run("my-command")
        self.assertIn("Hello custom command!", client.out)

    def user_command_no_command_test(self):
        client = TestClient()
        save(os.path.join(client.cache.cache_folder, "commands", "cmd_my_command.py"),
             self._command_file.format("some_name"))
        save(os.path.join(client.cache.cache_folder, "commands", "my_command_formatter.py"),
             self._formatter_file)
        client.run("help", assert_error=True)
        self.assertIn("ERROR: There is no my_command method defined in cmd_my_command", client.out)
