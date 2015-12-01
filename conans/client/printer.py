from conans.client.output import Color


class Printer(object):
    """ Print some specific information """

    INDENT_COLOR = {0: Color.BRIGHT_CYAN,
                    1: Color.BRIGHT_RED,
                    2: Color.BRIGHT_GREEN,
                    3: Color.BRIGHT_YELLOW,
                    4: Color.BRIGHT_MAGENTA}

    INDENT_SPACES = 4

    def __init__(self, out):
        self._out = out

    def print_graph(self, deps_graph):
        """ Simple pretty printing of a deps graph, can be improved
        with options, info like licenses, etc
        """
        self._out.writeln("Requirements", Color.BRIGHT_YELLOW)
        for node in sorted(deps_graph.nodes):
            ref, _ = node
            if not ref:
                continue
            self._out.writeln("    %s" % repr(ref), Color.BRIGHT_CYAN)

    def print_info(self, info, pattern=None, verbose=False):
        """ Print all the exported conans information
        param pattern: wildcards, e.g., "opencv/*"
        """
        if not info:
            warn_msg = "There are no packages"
            pattern_msg = " matching the %s pattern" % pattern
            self._out.info(warn_msg + pattern_msg if pattern else warn_msg)
            return

        self._out.info("Existing packages info:\n")
        for conan_ref, packages in sorted(info.iteritems()):
            self._print_colored_line(str(conan_ref), indent=0)
            if not packages:
                self._out.writeln('    There are no packages', Color.RED)
            for package_id, conan_info in packages.iteritems():
                self._print_colored_line("Package_ID", package_id, 1)
                if verbose:
                    # Printing the Package information (settings, options, requires, ...)
                    # Options
                    if conan_info.options:
                        self._print_colored_line("[options]", indent=2)
                        for option in conan_info.options.dumps().splitlines():
                            self._print_colored_line(option, indent=3)
                    # Settings
                    if conan_info.settings:
                        self._print_colored_line("[settings]", indent=2)
                        for settings in conan_info.settings.dumps().splitlines():
                            self._print_colored_line(settings, indent=3)
                    # Requirements
                    if conan_info.requires:
                        self._print_colored_line("[requirements]", indent=2)
                        for name in conan_info.requires.dumps().splitlines():
                            self._print_colored_line(str(name), indent=3)
                else:
                    if conan_info.settings:
                        settings_line = [values[1] for values in \
                                         [setting.split("=") for setting in conan_info.settings.dumps().splitlines()]]
                        settings_line = "(%s)" % ", ".join(settings_line)
                        self._print_colored_line(settings_line, indent=3)

    def _print_colored_line(self, text, value=None, indent=0):
        """ Print a colored line depending on its indentation level
            Attributes:
                text: string line
                split_symbol: if you want an output with different in-line colors
                indent_plus: integer to add a plus indentation
        """
        text = text.strip()
        if not text:
            return

        text_color = Printer.INDENT_COLOR.get(indent, Color.BRIGHT_WHITE)
        indent_text = ' ' * Printer.INDENT_SPACES * indent
        if value is not None:
            value_color = Color.BRIGHT_WHITE
            self._out.write('%s%s: ' % (indent_text, text), text_color)
            self._out.writeln(value, value_color)
        else:
            self._out.writeln('%s%s' % (indent_text, text), text_color)
