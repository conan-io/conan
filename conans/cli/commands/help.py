import argparse
import textwrap

from conans.client.output import Color
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
        _show_help(conan_api.out, commands, groups)
        return
    try:
        method = commands[args.command].method
        method(conan_api, ["--help"])
    except KeyError:
        raise ConanException("Unknown command '%s'" % args.command)


def _show_help(out, commands, groups):
    """
    Prints a summary of all commands.
    """
    max_len = max((len(c) for c in commands)) + 1
    fmt = '  %-{}s'.format(max_len)

    for group_name, comm_names in groups.items():
        out.writeln(group_name, Color.BRIGHT_MAGENTA)
        for name in comm_names:
            # future-proof way to ensure tabular formatting
            out.write(fmt % name, Color.GREEN)

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
            out.writeln(txt)

    out.writeln("")
    out.writeln('Conan commands. Type "conan <command> -h" for help', Color.BRIGHT_YELLOW)
