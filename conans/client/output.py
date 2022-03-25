import os
import six
import sys
from colorama import Fore, Style

from conans.util.env_reader import get_env
from conans.util.files import decode_text


def colorama_initialize():
    if "NO_COLOR" in os.environ:
        return False

    clicolor_force = get_env("CLICOLOR_FORCE")
    if clicolor_force is not None and clicolor_force != "0":
        import colorama
        colorama.init(convert=False, strip=False)
        return True

    isatty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    clicolor = get_env("CLICOLOR")
    if clicolor is not None:
        if clicolor == "0" or not isatty:
            return False
        import colorama
        colorama.init()
        return True

    # Respect color env setting or check tty if unset
    color_set = "CONAN_COLOR_DISPLAY" in os.environ
    if ((color_set and get_env("CONAN_COLOR_DISPLAY", 1))
            or (not color_set and isatty)):
        import colorama
        if get_env("PYCHARM_HOSTED"):  # in PyCharm disable convert/strip
            colorama.init(convert=False, strip=False)
        else:
            colorama.init()
        color = True
    else:
        color = False
    return color


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

    def _write(self, data, newline=False):
        if newline:
            data = "%s\n" % data
        self._stream.write(data)

    def _write_err(self, data, newline=False):
        if newline:
            data = "%s\n" % data
        self._stream_err.write(data)

    def write(self, data, front=None, back=None, newline=False, error=False):
        if six.PY2:
            if isinstance(data, str):
                data = decode_text(data)  # Keep python 2 compatibility

        if self._color and (front or back):
            data = "%s%s%s%s" % (front or '', back or '', data, Style.RESET_ALL)

        # https://github.com/conan-io/conan/issues/4277
        # Windows output locks produce IOErrors
        for _ in range(3):
            try:
                if error:
                    self._write_err(data, newline)
                else:
                    self._write(data, newline)
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

    warning = warn

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
        if self.scope == "virtual":
            return
        super(ScopedOutput, self).write("%s: " % self.scope, front=front, back=back,
                                        newline=False, error=error)
        super(ScopedOutput, self).write("%s" % data, front=Color.BRIGHT_WHITE, back=back,
                                        newline=newline, error=error)
