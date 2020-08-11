import logging
import os
import sys

import tqdm
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
    def __init__(self, stream=None, color=False):
        self._logger_name = "conan.output"
        self._stream = stream
        self._stream_handler = None

        if self._stream is None:
            logging.getLogger(self._logger_name).addHandler(NullHandler())
        else:
            self._stream_handler = TqdmHandler(self._stream)
            self._stream_handler.setFormatter(logging.Formatter("%(message)s"))
            logging.getLogger(self._logger_name).addHandler(self._stream_handler)
            logging.getLogger(self._logger_name).setLevel(logging.INFO)
            logging.getLogger(self._logger_name).propagate = False

            logging.captureWarnings(True)
            logging.getLogger("py.warnings").setLevel(logging.WARNING)
            logging.getLogger("py.warnings").addHandler(self._stream_handler)
            logging.getLogger("py.warnings").propagate = False

        self._color = color
        self._scope = None

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
        for _ in range(3):
            try:
                logging.getLogger(self._logger_name).log(level, msg)
                break
            except IOError:
                import time
                time.sleep(0.02)
            except UnicodeError:
                msg = msg.encode("utf8").decode("ascii", "ignore")

        self.flush()

    def debug(self, msg):
        self._write(msg, logging.DEBUG)

    def info(self, msg, fg=None, bg=None):
        self._write(msg, logging.INFO, fg, bg)

    def warning(self, msg):
        self._write("WARNING: {}".format(msg), logging.WARNING, Color.YELLOW)

    def error(self, msg):
        self._write("ERROR: {}".format(msg), logging.ERROR, Color.RED)

    def critical(self, msg):
        self._write("ERROR: {}".format(msg), logging.CRITICAL, Color.BRIGHT_RED)

    def flush(self):
        if self._stream_handler:
            self._stream_handler.flush()


class CliOutput(object):
    def __init__(self, stream, color=False):
        self._stream = stream
        self._color = color
        self._scope = None

    @property
    def color(self):
        return self._color

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

    def flush(self):
        self._stream.flush()
