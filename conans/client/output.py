from colorama import Fore, Back, Style
import six
from conans.util.files import decode_text


class Color(object):
    """ Wrapper around colorama colors that are undefined in importing
    """
    RED = Fore.RED  # @UndefinedVariable
    WHITE = Fore.WHITE  # @UndefinedVariable
    CYAN = Fore.CYAN  # @UndefinedVariable
    GREEN = Fore.GREEN  # @UndefinedVariable
    MAGENTA = Fore.MAGENTA  # @UndefinedVariable
    BLUE = Fore.BLUE  # @UndefinedVariable
    YELLOW = Fore.YELLOW  # @UndefinedVariable
    BLACK = Fore.BLACK  # @UndefinedVariable

    BRIGHT_RED = Style.BRIGHT + Fore.RED  # @UndefinedVariable
    BRIGHT_BLUE = Style.BRIGHT + Fore.BLUE  # @UndefinedVariable
    BRIGHT_YELLOW = Style.BRIGHT + Fore.YELLOW  # @UndefinedVariable
    BRIGHT_GREEN = Style.BRIGHT + Fore.GREEN  # @UndefinedVariable
    BRIGHT_CYAN = Style.BRIGHT + Fore.CYAN   # @UndefinedVariable
    BRIGHT_WHITE = Style.BRIGHT + Fore.WHITE   # @UndefinedVariable
    BRIGHT_MAGENTA = Style.BRIGHT + Fore.MAGENTA   # @UndefinedVariable

    BACK_YELLOW = Back.YELLOW  # @UndefinedVariable
    BACK_BLUE = Back.BLUE  # @UndefinedVariable
    BACK_BLACK = Back.BLACK  # @UndefinedVariable
    BACK_MAGENTA = Back.MAGENTA  # @UndefinedVariable
    BACK_CYAN = Back.CYAN  # @UndefinedVariable
    BACK_GREEN = Back.GREEN  # @UndefinedVariable
    BACK_RED = Back.RED  # @UndefinedVariable
    BACK_WHITE = Back.WHITE   # @UndefinedVariable


class ConanOutput(object):
    """ wraps an output stream, so it can be pretty colored,
    and auxiliary info, success, warn methods for convenience.
    """

    def __init__(self, stream, color=False):
        self._stream = stream
        self._color = color

    def writeln(self, data, front=None, back=None):
        self.write(data, front, back, True)

    def write(self, data, front=None, back=None, newline=False):
        if six.PY2:
            if isinstance(data, str):
                data = decode_text(data)  # Keep python 2 compatibility

        if self._color and (front or back):
            color = "%s%s" % (front or '', back or '')
            end = (Style.RESET_ALL + "\n") if newline else Style.RESET_ALL  # @UndefinedVariable
            self._stream.write("%s%s%s" % (color, data, end))
        else:
            if newline:
                data = "%s\n" % data
            self._stream.write(data)
        self._stream.flush()

    def info(self, data):
        self.writeln(data, Color.BRIGHT_CYAN)

    def success(self, data):
        self.writeln(data, Color.BRIGHT_GREEN)

    def warn(self, data):
        self.writeln("WARN: " + data, Color.BRIGHT_YELLOW)

    def error(self, data):
        self.writeln("ERROR: " + data, Color.BRIGHT_RED)

    def input_text(self, data):
        self.write(data, Color.GREEN)

    def rewrite_line(self, line):
        tmp_color = self._color
        self._color = False
        TOTAL_SIZE = 70
        if len(line) > TOTAL_SIZE:
            line = line[0:TOTAL_SIZE / 2 - 3] + " ... " + line[TOTAL_SIZE / 2 + 3:]
        self.write("\r%s%s" % (line, " " * (TOTAL_SIZE - len(line))))
        self._stream.flush()
        self._color = tmp_color


class ScopedOutput(ConanOutput):
    def __init__(self, scope, output):
        self.scope = scope
        self._stream = output._stream
        self._color = output._color

    def write(self, data, front=None, back=None, newline=False):
        super(ScopedOutput, self).write("%s: " % self.scope, front, back, False)
        super(ScopedOutput, self).write("%s" % data, Color.BRIGHT_WHITE, back, newline)
