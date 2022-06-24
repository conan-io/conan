import json
import os
from json import JSONEncoder

from conan.api.model import Remote
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


def json_formatter(data):
    myjson = json.dumps(data, indent=4, cls=ConanJSONEncoder)
    return myjson


def add_log_level_args(subparser):
    subparser.add_argument("-v", "--output-level",  default="status", nargs='?',
                           help="Level of detail of the output")
    subparser.add_argument("--sol", "--strict-output-level", action='store_true',
                           help="If specified, only the messages corresponding to the '-v' arg "
                                "will be shown")


def process_log_level_args(args):
    from conans.cli import output
    from conans.cli.output import LEVEL_QUIET, LEVEL_ERROR, LEVEL_WARNING, LEVEL_NOTICE, \
        LEVEL_STATUS, LEVEL_VERBOSE, LEVEL_DEBUG, LEVEL_TRACE

    levels = {None: LEVEL_VERBOSE,  # -v
              "verbose": LEVEL_VERBOSE,  # -vverbose
              "v": LEVEL_DEBUG,  # -vv
              "debug": LEVEL_DEBUG,  # -vdebug
              "vv": LEVEL_TRACE,  # -vvv
              "trace": LEVEL_TRACE,  # -vtrace
              "status": LEVEL_STATUS,  # -vstatus
              "notice": LEVEL_NOTICE,  # -vnotice
              "warning": LEVEL_WARNING,  # -vwaring
              "error": LEVEL_ERROR,  # -verror
              "quiet": LEVEL_QUIET  # -vquiet
              }

    level = levels.get(args.output_level)
    if not level:
        raise ConanException(f"Invalid argument '-v{args.output_level}'")
    output.conan_output_level = level
    output.conan_strict_output_level = args.sol
