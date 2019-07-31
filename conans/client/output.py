import os
import six
import sys
from colorama import Fore, Style, init as colorama_init

from conans.util.env_reader import get_env
from conans.util.files import decode_text


def colorama_initialize():
    # Respect color env setting or check tty if unset
    for var in ("CONAN_COLOR_DISPLAY", "PYCHARM_HOSTED"):
        if var in os.environ:
            force_color = get_env(var, False)
            color = force_color
            break
    else:
        force_color = False
        color = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    if color:
        if force_color:
            colorama_init(convert=False, strip=False)
        else:
            colorama_init()

    return bool(color)


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


if get_env("CONAN_COLOR_DARK", 0):
    Color.WHITE = Fore.BLACK
    Color.CYAN = Fore.BLUE
    Color.YELLOW = Fore.MAGENTA
    Color.BRIGHT_WHITE = Fore.BLACK
    Color.BRIGHT_CYAN = Fore.BLUE
    Color.BRIGHT_YELLOW = Fore.MAGENTA
    Color.BRIGHT_GREEN = Fore.GREEN


class ConanOutput(object):
    """ wraps an output stream, so it can be pretty colored,
    and auxiliary info, success, warn methods for convenience.
    """

    def __init__(self, stream, stream_err=None, color=False):
        self._stream = stream
        self._stream_err = stream_err or stream
        self._color = color

    @property
    def is_terminal(self):
        return hasattr(self._stream, "isatty") and self._stream.isatty()

    def writeln(self, data, front=None, back=None, error=False):
        self.write(data, front, back, newline=True, error=error)

    def write(self, data, front=None, back=None, newline=False, error=False):
        if six.PY2:
            if isinstance(data, str):
                data = decode_text(data)  # Keep python 2 compatibility

        if self._color and (front or back):
            data = "%s%s%s%s" % (front or '', back or '', data, Style.RESET_ALL)
        if newline:
            data = "%s\n" % data

        # https://github.com/conan-io/conan/issues/4277
        # Windows output locks produce IOErrors
        for _ in range(3):
            try:
                if error:
                    self._stream_err.write(data)
                else:
                    self._stream.write(data)
                break
            except IOError:
                import time
                time.sleep(0.02)
            except UnicodeError:
                data = data.encode("utf8").decode("ascii", "ignore")

        self._stream.flush()

    def info(self, data):
        self.writeln(data, Color.BRIGHT_CYAN)

    def highlight(self, data):
        self.writeln(data, Color.BRIGHT_MAGENTA)

    def success(self, data):
        self.writeln(data, Color.BRIGHT_GREEN)

    def warn(self, data):
        self.writeln("WARN: {}".format(data), Color.BRIGHT_YELLOW, error=True)

    def error(self, data):
        self.writeln("ERROR: {}".format(data), Color.BRIGHT_RED, error=True)

    def input_text(self, data):
        self.write(data, Color.GREEN)

    def rewrite_line(self, line):
        tmp_color = self._color
        self._color = False
        TOTAL_SIZE = 70
        LIMIT_SIZE = 32  # Hard coded instead of TOTAL_SIZE/2-3 that fails in Py3 float division
        if len(line) > TOTAL_SIZE:
            line = line[0:LIMIT_SIZE] + " ... " + line[-LIMIT_SIZE:]
        self.write("\r%s%s" % (line, " " * (TOTAL_SIZE - len(line))))
        self._stream.flush()
        self._color = tmp_color

    def flush(self):
        self._stream.flush()


class ScopedOutput(ConanOutput):
    def __init__(self, scope, output):
        self.scope = scope
        self._stream = output._stream
        self._stream_err = output._stream_err
        self._color = output._color

    def write(self, data, front=None, back=None, newline=False, error=False):
        assert self.scope != "virtual", "printing with scope==virtual"
        super(ScopedOutput, self).write("%s: " % self.scope, front=front, back=back,
                                        newline=False, error=error)
        super(ScopedOutput, self).write("%s" % data, front=Color.BRIGHT_WHITE, back=back,
                                        newline=newline, error=error)
