import argparse

import pytest
from mock import patch

from conan import __version__
from conan.test.utils.env import environment_update
from conan.test.utils.tools import TestClient


class TestHelp:

    def test_version(self):
        c = TestClient()
        c.run("--version")
        assert "Conan version %s" % __version__ in c.out

    def test_unknown_command(self):
        c = TestClient()
        c.run("some_unknown_command123", assert_error=True)
        assert "'some_unknown_command123' is not a Conan command" in c.out

    def test_similar(self):
        c = TestClient()
        c.run("instal", assert_error=True)
        assert "The most similar command is" in c.out
        assert "install" in c.out

        c.run("remole", assert_error=True)
        assert "The most similar commands are" in c.out
        assert "remove" in c.out
        assert "remote" in c.out

    def test_help(self):
        c = TestClient()
        c.run("-h")
        assert "Creator commands" in c.out
        assert "Consumer commands" in c.out

    def test_help_command(self):
        c = TestClient()
        c.run("new -h")
        assert "Create a new example recipe" in c.out

    def test_help_subcommand(self):
        c = TestClient()
        c.run("cache -h")
        # When listing subcommands, but line truncated
        assert "Perform file operations in the local cache (of recipes and/or packages)" in c.out
        c.run("cache path -h")
        assert "Show the path to the Conan cache for a given reference" in c.out


def test_all_commands_call_args_parse():
    tc = TestClient(light=True)
    tc.run("-h")
    commands = tc.api.command.cli._builtin_commands
    with environment_update({"CONAN_WORKSPACE_ENABLE": "will_break_next"}):
        for command, info in commands.items():
            if len(info._subcommands) > 0:
                for subcommand in info._subcommands.values():
                    with patch("conan.cli.command.ConanArgumentParser.parse_args",
                               side_effect=Exception("called")) as mock_run:
                        try:
                            tc.run(f"{command} {subcommand.name} -h")
                        except:
                            pass
                        finally:
                            assert mock_run.called, f'Command "conan {command} {subcommand.name}" did not call parse_args()'
            else:
                with patch("conan.cli.command.ConanArgumentParser.parse_args",
                           side_effect=Exception("called")) as mock_run:
                    try:
                        tc.run(f"{command} -h")
                    except:
                        pass
                    finally:
                        assert mock_run.called, f'Command "conan {command}" did not call parse_args()'
