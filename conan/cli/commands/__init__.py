import json
import os
from json import JSONEncoder

from conan.api.model import Remote
from conan.api.output import cli_out_write
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


def make_abs_path(path, cwd=None):
    """convert 'path' to absolute if necessary (could be already absolute)
    if not defined (empty, or None), will return 'default' one or 'cwd'
    """
    if path is None:
        return None
    if os.path.isabs(path):
        return path
    cwd = cwd or os.getcwd()
    abs_path = os.path.normpath(os.path.join(cwd, path))
    return abs_path


class ConanJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, (RecipeReference, PkgReference)):
            return repr(o)
        elif isinstance(o, Remote):
            return o.name
        return JSONEncoder.default(self, o)


def default_json_formatter(data):
    myjson = json.dumps(data, indent=4, cls=ConanJSONEncoder)
    cli_out_write(myjson)


def default_text_formatter(data):
    cli_out_write(data)


def add_log_level_args(subparser):
    subparser.add_argument("-v", default="status", nargs='?',
                           help="Level of detail of the output. Valid options from less verbose "
                                "to more verbose: -vquiet, -verror, -vwarning, -vnotice, -vstatus, "
                                "-v or -vverbose, -vv or -vdebug, -vvv or -vtrace")
    subparser.add_argument("--logger", action="store_true",
                           help="Show the output with log format, with time, type and message.")


def process_log_level_args(args):
    from conan.api import output
    from conan.api.output import LEVEL_QUIET, LEVEL_ERROR, LEVEL_WARNING, LEVEL_NOTICE, \
        LEVEL_STATUS, LEVEL_VERBOSE, LEVEL_DEBUG, LEVEL_TRACE

    levels = {"quiet": LEVEL_QUIET,  # -vquiet 80
              "error": LEVEL_ERROR,  # -verror 70
              "warning": LEVEL_WARNING,  # -vwaring 60
              "notice": LEVEL_NOTICE,  # -vnotice 50
              "status": LEVEL_STATUS,  # -vstatus 40
              "verbose": LEVEL_VERBOSE,  # -vverbose 30
              None: LEVEL_VERBOSE,  # -v 30
              "debug": LEVEL_DEBUG,  # -vdebug 20
              "v": LEVEL_DEBUG,  # -vv 20
              "trace": LEVEL_TRACE,  # -vtrace 10
              "vv": LEVEL_TRACE,  # -vvv 10
              }

    level = levels.get(args.v)
    if not level:
        raise ConanException(f"Invalid argument '-v{args.v}'")
    output.conan_output_level = level
    output.conan_output_logger_format = args.logger
