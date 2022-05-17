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
