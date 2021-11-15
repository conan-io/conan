import logging
import sys

import tqdm
from colorama import Fore, Style

from conans.client.userio import color_enabled
from conans.util.env_reader import get_env


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

try:
    from logging import NullHandler
except ImportError:  # TODO: Remove if Python > 3.1
    class NullHandler(logging.Handler):
        def handle(self, record):
            pass

        def emit(self, record):
            pass

        def createLock(self):
            self.lock = None


class ConanOutput(object):
    def __init__(self):
        self.stream = sys.stderr
        self._scope = ""
        self._color = color_enabled(self.stream)

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
        return hasattr(self.stream, "isatty") and self.stream.isatty()

    def writeln(self, data, fg=None, bg=None):
        self.write(data, fg, bg, newline=True)

    def write(self, data, fg=None, bg=None, newline=False):
        if self._color and (fg or bg):
            data = "%s%s%s%s" % (fg or '', bg or '', data, Style.RESET_ALL)

        # https://github.com/conan-io/conan/issues/4277
        # Windows output locks produce IOErrors
        for _ in range(3):
            try:
                if newline:
                    data = "%s\n" % data
                self.stream.write(data)
                break
            except IOError:
                import time
                time.sleep(0.02)
            except UnicodeError:
                data = data.encode("utf8").decode("ascii", "ignore")

        self.stream.flush()

    def rewrite_line(self, line):
        tmp_color = self._color
        self._color = False
        TOTAL_SIZE = 70
        LIMIT_SIZE = 32  # Hard coded instead of TOTAL_SIZE/2-3 that fails in Py3 float division
        if len(line) > TOTAL_SIZE:
            line = line[0:LIMIT_SIZE] + " ... " + line[-LIMIT_SIZE:]
        self.write("\r%s%s" % (line, " " * (TOTAL_SIZE - len(line))))
        self.stream.flush()
        self._color = tmp_color

    def _write_message(self, msg, fg=None, bg=None):
        tmp = ""
        if self._scope:
            if self._color:
                tmp = "{}{}{}:{} ".format(fg or '', bg or '', self.scope, Style.RESET_ALL)
            else:
                tmp = "{}: ".format(self._scope)

        if self._color and not self._scope:
            tmp += "{}{}{}{}".format(fg or '', bg or '', msg, Style.RESET_ALL)
        else:
            tmp += "{}".format(msg)

        self.stream.write("{}\n".format(tmp))

    def debug(self, msg):
        self._write_message(msg, logging.DEBUG)

    def info(self, msg, fg=None, bg=None):
        self._write_message(msg, fg=fg, bg=bg)

    def highlight(self, data):
        self.info(data, fg=Color.BRIGHT_MAGENTA)

    def success(self, data):
        self.info(data, fg=Color.BRIGHT_GREEN)

    def warning(self, msg):
        self._write_message("WARN: {}".format(msg), Color.YELLOW)

    def error(self, msg):
        self._write_message("ERROR: {}".format(msg), Color.RED)

    def critical(self, msg):
        self._write_message("ERROR: {}".format(msg), Color.BRIGHT_RED)

    def flush(self):
        self.stream.flush()


class ScopedOutput(ConanOutput):

    def __init__(self, scope, output):
        ConanOutput.__init__(self)
        self._scope = scope
        self._color = output._color


def cli_out_write(data, fg=None, bg=None, endline="\n", indentation=0):
    fg_ = fg or ''
    bg_ = bg or ''
    if color_enabled(sys.stdout):
        data = f"{' ' * indentation}{fg_}{bg_}{data}{Style.RESET_ALL}{endline}"
    else:
        data = f"{' ' * indentation}{data}{endline}"

    sys.stdout.write(data)
