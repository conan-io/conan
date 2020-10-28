import logging
import sys

import tqdm
from colorama import Fore, Style

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


class TqdmHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        self._stream = stream
        super(TqdmHandler, self).__init__(stream)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.tqdm.write(msg, file=self._stream)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class ConanOutput(object):
    def __init__(self, quiet=False):
        self._logger = logging.getLogger("conan_out_logger")
        self._stream_handler = None
        self._quiet = quiet
        self._color = self._init_colors()

        if self._quiet:
            self._logger.addHandler(NullHandler())
        else:
            self._stream = sys.stderr
            self._stream_handler = TqdmHandler(self._stream)
            self._stream_handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(self._stream_handler)
            self._logger.setLevel(logging.INFO)
            self._logger.propagate = False

        self._scope = ""

    @property
    def stream(self):
        return self._stream

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

    def _write(self, msg, level, fg=None, bg=None):
        if self._scope:
            msg = "{}: {}".format(self.scope, msg)
        if self._color:
            msg = "{}{}{}{}".format(fg or '', bg or '', msg, Style.RESET_ALL)
        self._logger.log(level, msg)

    def debug(self, msg):
        self._write(msg, logging.DEBUG)

    def info(self, msg, fg=None, bg=None):
        self._write(msg, logging.INFO, fg, bg)

    # TODO: remove, just to support the migration system warn message
    def warn(self, msg):
        self._write("WARNING: {}".format(msg), logging.WARNING, Color.YELLOW)

    def warning(self, msg):
        self._write("WARNING: {}".format(msg), logging.WARNING, Color.YELLOW)

    def error(self, msg):
        self._write("ERROR: {}".format(msg), logging.ERROR, Color.RED)

    def critical(self, msg):
        self._write("ERROR: {}".format(msg), logging.CRITICAL, Color.BRIGHT_RED)

    def flush(self):
        if self._stream_handler:
            self._stream_handler.flush()

    @staticmethod
    def _init_colors():
        clicolor = get_env("CLICOLOR")
        clicolor_force = get_env("CLICOLOR_FORCE")
        no_color = get_env("NO_COLOR")
        if no_color or (clicolor and clicolor == "0"):
            import colorama
            colorama.init(strip=True)
            return False
        else:
            import colorama
            if clicolor_force or (clicolor and clicolor != "0"):
                colorama.init(convert=False, strip=False)
            else:
                # TODO: check if colorama checks for stripping colors are enough
                colorama.init()
            return True
