import copy
import json
import os
from json import JSONEncoder
from typing import List

from conans.cli.api.model import Remote, PkgConfiguration
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


class CommandResult(dict):
    """ This can be serialized to JSON automatically """

    def __init__(self, remote=None, error=None, elements=None):
        self["remote"] = remote
        self["error"] = error
        self["elements"] = elements
        dict.__init__(self)

    @property
    def error(self):
        return self["error"]

    @error.setter
    def error(self, value):
        self["error"] = value

    @property
    def remote(self):
        return self["remote"]

    @remote.setter
    def remote(self, value):
        self["remote"] = value

    @property
    def elements(self):
        return self["elements"]

    @elements.setter
    def elements(self, value):
        self["elements"] = value


class ConanJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, (RecipeReference, PkgReference)):
            return repr(o)
        elif isinstance(o, Remote):
            return o.name
        elif isinstance(o, PkgConfiguration):
            return {"settings": o.settings, "options": o.options, "requires": o.requires}
        raise TypeError("Don't know how to serialize a {} object".format(o.__class__))


def _fix_dict_keys(result: CommandResult):
    """
    There is no way to override the JSONEncoder to manage the dict keys if they are not
    serializable, and there is no way to write a method in the class to make it understandable by
    the json serializer, so we have to fix the dict first.
    """
    _tmp = copy.copy(result)
    if hasattr(_tmp, "elements") and isinstance(_tmp.elements, dict):
        new_elements = {}
        for key, value in _tmp.elements.items():
            if isinstance(key, (RecipeReference, PkgReference)):
                new_elements[repr(key)] = value
            else:
                new_elements[key] = value
        _tmp.elements = new_elements
    return _tmp


def json_formatter(data: List[CommandResult]):
    _data = [_fix_dict_keys(result) for result in data]
    myjson = json.dumps(_data, indent=4, cls=ConanJSONEncoder)
    return myjson
