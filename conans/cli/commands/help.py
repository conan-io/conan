from conans.cli.formatters.help_formatter import HelpFormatter
from conans.errors import ConanException
from conans.cli.command import conan_command


@conan_command(group="Misc commands")
def help(conan_api, parser, commands, groups, *args, **kwargs):
    """
    Shows help for a specific command.
    """

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
