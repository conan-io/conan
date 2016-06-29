import logging
from logging import StreamHandler
import sys
from conans.util.env_reader import get_env

# #### LOGGER, MOVED FROM CONF BECAUSE OF MULTIPLE PROBLEM WITH CIRCULAR INCLUDES #####
CONAN_LOGGING_LEVEL = get_env('CONAN_LOGGING_LEVEL', logging.CRITICAL)
CONAN_LOGGING_FILE = get_env('CONAN_LOGGING_FILE', None)  # None is stdout


class MultiLineFormatter(logging.Formatter):
    def format(self, record):
        str_ = logging.Formatter.format(self, record)
        separator = record.message if record.message else None
        if separator is None:
            return separator
        tmp = str_.split(separator)
        if len(tmp) == 2:
            header, _ = tmp
        else:
            header = tmp
        str_ = str_.replace('\n', '\n' + ' ' * len(header))
        return str_

logger = logging.getLogger('conans')
if CONAN_LOGGING_FILE is not None:
    hdlr = logging.FileHandler(CONAN_LOGGING_FILE)
else:
    hdlr = StreamHandler(sys.stderr)

formatter = MultiLineFormatter('%(levelname)-6s:%(filename)-15s[%(lineno)d]: '
                               '%(message)s [%(asctime)s]')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(CONAN_LOGGING_LEVEL)


# CRITICAL = 50
# FATAL = CRITICAL
# ERROR = 40
# WARNING = 30
# WARN = WARNING
# INFO = 20
# DEBUG = 10
# NOTSET = 0
