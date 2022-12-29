import unittest
import textwrap

from conans import __version__
from conans.test.utils.tools import TestClient


class BasicClientTest(unittest.TestCase):

    def test_help(self):
        client = TestClient()
        client.run("")
        self.assertIn('Conan commands. Type "conan <command> -h" for help', client.out)

        client.run("--version")
        self.assertIn("Conan version %s" % __version__, client.out)

        client.run("some_unknown_command123", assert_error=True)
        self.assertIn("ERROR: Unknown command 'some_unknown_command123'", client.out)

    def test_unknown_command(self):
        client = TestClient()

        client.run("some_unknown_command123", assert_error=True)
        expected_output = textwrap.dedent(
            """\
                'some_unknown_command123' is not a Conan command. See 'conan --help'.

                ERROR: Unknown command 'some_unknown_command123'
            """)
        self.assertIn(
            expected_output, client.out)

        # Check for a single suggestion
        client.run("instal", assert_error=True)

        expected_output = textwrap.dedent(
            """\
                'instal' is not a Conan command. See 'conan --help'.

                The most similar command is
                    install

                ERROR: Unknown command 'instal'
            """)
        self.assertIn(
            expected_output, client.out)

        # Check for multiple suggestions
        client.run("remoe", assert_error=True)
        self.assertIn(
            "", client.out)

        expected_output = textwrap.dedent(
            """\
                'remoe' is not a Conan command. See 'conan --help'.

                The most similar commands are
                    remove
                    remote

                ERROR: Unknown command 'remoe'
            """)
        self.assertIn(
            expected_output, client.out)

    def test_help_cmd(self):
        client = TestClient()
        client.run("help new")
        self.assertIn("Creates a new package recipe template with a 'conanfile.py'", client.out)

        client.run("help build")
        self.assertIn("Calls your local conanfile.py 'build()' method", client.out)

        client.run("help")
        self.assertIn("Creator commands", client.out)

    def test_help_cmd_error(self):
        client = TestClient()
        client.run("help not-exists", assert_error=True)
        self.assertIn("ERROR: Unknown command 'not-exists'", client.out)
