import textwrap

from conans.cli.formatters.base_formatter import BaseFormatter
from conans.client.output import Color


class HelpFormatter(BaseFormatter):

    @classmethod
    def cli(cls, out, commands, groups):
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
