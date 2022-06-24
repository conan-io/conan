import json
import os
from json import JSONEncoder

from conan.api.model import Remote
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
    # FIXME: Arguments name suggestions
    subparser.add_argument("-oe", "--errors", action='store_true',
                           help="Display error messages")
    subparser.add_argument("-ow", "--warnings", action='store_true',
                           help="Display warning messages")
    subparser.add_argument("-on", "--notice", action='store_true',
                           help="Display important messages to attract user attention")
    subparser.add_argument("-v", "--verbose", action='store_true',
                           help="Display detailed information messages")
    subparser.add_argument("-vv", action='store_true',
                           help="Display closely related to internal implementation details "
                                "messages")
    subparser.add_argument("-vvv", action='store_true',
                           help="Display fine-grained messages with very low-level implementation "
                                "details")
    subparser.add_argument("-q", "--quiet", action='store_true', help="Display no output")


def process_log_level_args(args):
    from conans.cli import output
    from conans.cli.output import LEVEL_ERROR, LEVEL_WARNING, LEVEL_NOTICE, LEVEL_TRACE, \
        LEVEL_DEBUG, LEVEL_VERBOSE, LEVEL_QUIET

    if args.errors:
        output.conan_log_level = LEVEL_ERROR
    elif args.warnings:
        output.conan_log_level = LEVEL_WARNING
    if args.notice:
        output.conan_log_level = LEVEL_NOTICE
    elif args.vvv:
        output.conan_log_level = LEVEL_TRACE
    elif args.vv:
        output.conan_log_level = LEVEL_DEBUG
    elif args.verbose:
        output.conan_log_level = LEVEL_VERBOSE
    elif args.quiet:
        output.conan_log_level = LEVEL_QUIET

