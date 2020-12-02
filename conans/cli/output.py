import logging
import os
import sys

import tqdm
from colorama import Fore, Style

from conans.errors import ConanException
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


class ColorFormatter(logging.Formatter):
    level_color = {
        'WARNING': Color.YELLOW,
        'DEBUG': Color.BLUE,
        'CRITICAL': Color.YELLOW,
        'ERROR': Color.RED
    }

    def __init__(self, msg, use_color=False, **kwargs):
        logging.Formatter.__init__(self, msg, **kwargs)
        self._use_color = use_color

    def format(self, record):
        msg = super(ColorFormatter, self).format(record)
        if self._use_color and record.levelname in self.level_color:
            msg = "{}{}{}".format(self.level_color[record.levelname], msg, Style.RESET_ALL)
        return msg


class ConanOutput(object):
    def __init__(self, quiet=False):
        self._logger = logging.getLogger("conan_out_logger")
        self._stream_handler = None
        self._file_handler = None
        self._quiet = quiet
        self._color = self._init_colors()

        if self._quiet:
            self._logger.addHandler(NullHandler())
        else:
            self._stream = sys.stderr
            self._stream_handler = TqdmHandler(self._stream)
            self._stream_handler.setFormatter(ColorFormatter("%(message)s", use_color=self._color))
            self._logger.addHandler(self._stream_handler)

            # TODO: Check for 2.0 if we want to use CONAN_TRACE_FILE or any other variable
            trace_path = os.environ.get("CONAN_TRACE_FILE", None)
            if trace_path:
                try:
                    self._file_handler = logging.FileHandler(trace_path)
                except:
                    raise ConanException("Bad CONAN_TRACE_FILE value. The specified "
                                         "path has to be an absolute path to a file.")
                self._file_handler.setLevel(logging.DEBUG)
                file_formatter = ColorFormatter("{{'time':{asctime}, logger_name:'{name}', "
                                                "level:'{levelname}', message:{message!r}}}",
                                                style="{", use_color=False)
                self._file_handler.setFormatter(file_formatter)
                self._logger.addHandler(self._file_handler)

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

    def _write(self, msg, level):
        if self._scope:
            msg = "{}: {}".format(self.scope, msg)
        self._logger.log(level, msg)

    def debug(self, msg):
        self._write(msg, logging.DEBUG)

    def info(self, msg):
        self._write(msg, logging.INFO)

    # TODO: remove, just to support the migration system warn message
    def warn(self, msg):
        self._write("WARNING: {}".format(msg), logging.WARNING)

    def warning(self, msg):
        self._write("WARNING: {}".format(msg), logging.WARNING)

    def error(self, msg):
        self._write("ERROR: {}".format(msg), logging.ERROR)

    def critical(self, msg):
        self._write("ERROR: {}".format(msg), logging.CRITICAL)

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
