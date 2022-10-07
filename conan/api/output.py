import json
import sys

from colorama import Fore, Style

from conans.client.userio import color_enabled
from conans.util.env import get_env

LEVEL_QUIET = 80  # -q

LEVEL_ERROR = 70  # Errors
LEVEL_WARNING = 60  # Warnings
LEVEL_NOTICE = 50  # Important messages to attract user attention.
LEVEL_STATUS = 40  # Default - The main interesting messages that users might be interested in.
LEVEL_VERBOSE = 30  # -v  Detailed informational messages.
LEVEL_DEBUG = 20  # -vv Closely related to internal implementation details
LEVEL_TRACE = 10  # -vvv Fine-grained messages with very low-level implementation details


# Singletons
conan_output_level = LEVEL_STATUS
conan_output_logger_format = False


def log_level_allowed(level):
    return conan_output_level <= level


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


class ConanOutput:
    def __init__(self, scope=""):
        self.stream = sys.stderr
        self._scope = scope
        # FIXME:  This is needed because in testing we are redirecting the sys.stderr to a buffer
        #         stream to capture it, so colorama is not there to strip the color bytes
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
        if conan_output_level > LEVEL_NOTICE:
            return
        if self._color and (fg or bg):
            data = "%s%s%s%s" % (fg or '', bg or '', data, Style.RESET_ALL)

        if newline:
            data = "%s\n" % data
        self.stream.write(data)
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

    def _write_message(self, msg, level_str, fg=None, bg=None):
        if conan_output_level == LEVEL_QUIET:
            return

        def json_encoder(_obj):
            try:
                return json.dumps(_obj)
            except TypeError:
                return repr(_obj)

        if conan_output_logger_format:
            import datetime
            the_date = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
            ret = {"json": {"level": level_str, "time": the_date, "data": msg}}
            ret = json.dumps(ret, default=json_encoder)
            self.stream.write("{}\n".format(ret))
            return

        if isinstance(msg, dict):
            # For traces we can receive a dict already, we try to transform then into more natural
            # text
            msg = ", ".join([f"{k}: {v}" for k, v in msg.items()])
            msg = "=> {}".format(msg)
            # msg = json.dumps(msg, sort_keys=True, default=json_encoder)

        ret = ""
        if self._scope:
            if self._color:
                ret = "{}{}{}:{} ".format(fg or '', bg or '', self.scope, Style.RESET_ALL)
            else:
                ret = "{}: ".format(self._scope)

        if self._color and not self._scope:
            ret += "{}{}{}{}".format(fg or '', bg or '', msg, Style.RESET_ALL)
        else:
            ret += "{}".format(msg)

        self.stream.write("{}\n".format(ret))

    def trace(self, msg):
        if log_level_allowed(LEVEL_TRACE):
            self._write_message(msg, "TRACE", fg=Color.BRIGHT_WHITE)

    def debug(self, msg):
        if log_level_allowed(LEVEL_DEBUG):
            self._write_message(msg, "DEBUG")

    def verbose(self, msg, fg=None, bg=None):
        if log_level_allowed(LEVEL_VERBOSE):
            self._write_message(msg, "VERBOSE", fg=fg, bg=bg)

    def status(self, msg, fg=None, bg=None):
        if log_level_allowed(LEVEL_STATUS):
            self._write_message(msg, "STATUS", fg=fg, bg=bg)

    # Remove in a later refactor of all the output.info calls
    info = status

    def title(self, msg):
        if log_level_allowed(LEVEL_NOTICE):
            self._write_message("\n-------- {} --------".format(msg), "NOTICE",
                                fg=Color.BRIGHT_MAGENTA)

    def highlight(self, msg):
        if log_level_allowed(LEVEL_NOTICE):
            self._write_message(msg, "NOTICE", fg=Color.BRIGHT_MAGENTA)

    def success(self, msg):
        if log_level_allowed(LEVEL_NOTICE):
            self._write_message(msg, "NOTICE", fg=Color.BRIGHT_GREEN)

    def warning(self, msg):
        if log_level_allowed(LEVEL_WARNING):
            self._write_message("WARN: {}".format(msg), "WARN", Color.YELLOW)

    def error(self, msg):
        if log_level_allowed(LEVEL_ERROR):
            self._write_message("ERROR: {}".format(msg), "ERROR", Color.RED)

    def flush(self):
        self.stream.flush()


def cli_out_write(data, fg=None, bg=None, endline="\n", indentation=0):
    """
    Output to be used by formatters to dump information to stdout
    """

    fg_ = fg or ''
    bg_ = bg or ''
    if color_enabled(sys.stdout):
        data = f"{' ' * indentation}{fg_}{bg_}{data}{Style.RESET_ALL}{endline}"
    else:
        data = f"{' ' * indentation}{data}{endline}"

    sys.stdout.write(data)
