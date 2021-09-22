import textwrap

from conans.cli.output import cli_out_write, Color
from conans.errors import ConanException
from conans.cli.command import conan_command


def output_help_cli(commands, groups):
    """
    Prints a summary of all commands.
    """
    max_len = max((len(c) for c in commands)) + 1
    format = '{{: <{}}}'.format(max_len)

    for group_name, comm_names in groups.items():
        cli_out_write(group_name, Color.BRIGHT_MAGENTA)
        for name in comm_names:
            # future-proof way to ensure tabular formatting
            cli_out_write(format.format(name), Color.GREEN, endline="")

            # Help will be all the lines up to the first empty one
            docstring_lines = commands[name].doc.split('\n')
            start = False
            data = []
            for line in docstring_lines:
                line = line.strip()
                if not line:
                    if start:
                        break
                    start = True
                    continue
                data.append(line)

            txt = textwrap.fill(' '.join(data), 80, subsequent_indent=" " * (max_len + 2))
            cli_out_write(txt)

    cli_out_write("")
    cli_out_write('Conan commands. Type "conan help <command>" for help', Color.BRIGHT_YELLOW)


@conan_command(formatters={"cli": output_help_cli})
def help(conan_api, parser, *args, commands, groups, **kwargs):
    """
    Shows help for a specific command.
    """

    parser.add_argument("command", help='command', nargs="?")
    args = parser.parse_args(*args)
    if not args.command:
        output_help_cli(commands, groups)
        return None
    try:
        commands[args.command].run(conan_api, commands[args.command].parser, ["--help"])
    except KeyError:
        raise ConanException("Unknown command '%s'" % args.command)
