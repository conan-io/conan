import os
import sys

from colorama import Fore, Style

from conans.util.env_reader import get_env


def should_color_output():
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
    BRIGHT_CYAN = Style.BRIGHT + Fore.CYAN  # @UndefinedVariable
    BRIGHT_WHITE = Style.BRIGHT + Fore.WHITE  # @UndefinedVariable
    BRIGHT_MAGENTA = Style.BRIGHT + Fore.MAGENTA  # @UndefinedVariable


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

    def __init__(self, stream, color=False):
        self._stream = stream
        self._color = color
        self._scope = None

    @property
    def color(self):
        return self._color

    @property
    def scope(self):
        return self._scope

    @scope.setter
    def scope(self, out_scope):
        self._scope = out_scope

    @property
    def is_terminal(self):
        return hasattr(self._stream, "isatty") and self._stream.isatty()

    def write(self, data, fg=None, bg=None, newline=True):
        # https://github.com/conan-io/conan/issues/4277
        # Windows output locks produce IOErrors
        if self._scope:
            data = "{}: {}".format(self.scope, data)
        if self._color:
            data = "{}{}{}{}".format(fg or '', bg or '', data, Style.RESET_ALL)
        for _ in range(3):
            try:
                self._write(data, newline)
                break
            except IOError:
                import time
                time.sleep(0.02)
            except UnicodeError:
                data = data.encode("utf8").decode("ascii", "ignore")
        self.flush()

    def _write(self, message, newline=True):
        message = "{}\n".format(message) if newline else message
        self._stream.write(message)

    def debug(self, data):
        self.write(data)

    def info(self, data):
        self.write(data)

    def warning(self, data):
        self.write("WARNING: {}".format(data), Color.BRIGHT_YELLOW)

    def error(self, data):
        self.write("ERROR: {}".format(data), Color.BRIGHT_RED)

    def critical(self, data):
        self.write("ERROR: {}".format(data), Color.BRIGHT_RED)

    def flush(self):
        self._stream.flush()
