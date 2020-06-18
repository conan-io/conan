import argparse

from conans.client.formatters.help_formatter import HelpFormatter
from conans.errors import ConanException
from conans.cli.command import SmartFormatter, conan_command


@conan_command(group="Misc commands")
def help(conan_api, commands, groups, *args):
    """
    Shows help for a specific command.
    """
    parser = argparse.ArgumentParser(description=help.__doc__, prog="conan help",
                                     formatter_class=SmartFormatter)
    parser.add_argument("command", help='command', nargs="?")
    args = parser.parse_args(*args)
    if not args.command:
        HelpFormatter.out("cli", conan_api.out, commands, groups)
        return
    try:
        method = commands[args.command].method
        method(conan_api, ["--help"])
    except KeyError:
        raise ConanException("Unknown command '%s'" % args.command)
