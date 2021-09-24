import os
from collections import OrderedDict
from copy import copy

from conans.errors import ConanException
from conans.util.conan_v2_mode import conan_v2_error

DEFAULT_INCLUDE = "include"
DEFAULT_LIB = "lib"
DEFAULT_BIN = "bin"
DEFAULT_RES = "res"
DEFAULT_SHARE = "share"
DEFAULT_BUILD = ""
DEFAULT_FRAMEWORK = "Frameworks"

COMPONENT_SCOPE = "::"


class DefaultOrderedDict(OrderedDict):

    def __init__(self, factory):
        self.factory = factory
        super(DefaultOrderedDict, self).__init__()

    def __getitem__(self, key):
        if key not in self.keys():
            super(DefaultOrderedDict, self).__setitem__(key, self.factory())
            super(DefaultOrderedDict, self).__getitem__(key).name = key
        return super(DefaultOrderedDict, self).__getitem__(key)

    def __copy__(self):
        the_copy = DefaultOrderedDict(self.factory)
        for key, value in super(DefaultOrderedDict, self).items():
            the_copy[key] = value
        return the_copy


class BuildModulesDict(dict):
    """
    A dictionary with append and extend for cmake build modules to keep it backwards compatible
    with the list interface
    """

    def __getitem__(self, key):
        if key not in self.keys():
            super(BuildModulesDict, self).__setitem__(key, list())
        return super(BuildModulesDict, self).__getitem__(key)

    def _append(self, item):
        if item.endswith(".cmake"):
            self["cmake"].append(item)
            self["cmake_multi"].append(item)
            self["cmake_find_package"].append(item)
            self["cmake_find_package_multi"].append(item)

    def append(self, item):
        conan_v2_error("Use 'self.cpp_info.build_modules[\"<generator>\"].append(\"{item}\")' "
                       'instead'.format(item=item))
        self._append(item)

    def extend(self, items):
        conan_v2_error("Use 'self.cpp_info.build_modules[\"<generator>\"].extend({items})' "
                       "instead".format(items=items))
        for item in items:
            self._append(item)

    @classmethod
    def from_list(cls, build_modules):
        the_dict = BuildModulesDict()
        the_dict.extend(build_modules)
        return the_dict


def dict_to_abs_paths(the_dict, rootpath):
    new_dict = {}
    for generator, values in the_dict.items():
        new_dict[generator] = [os.path.join(rootpath, p) if not os.path.isabs(p) else p
                               for p in values]
    return new_dict


def merge_lists(seq1, seq2):
    return seq1 + [s for s in seq2 if s not in seq1]


def merge_dicts(d1, d2):
    def merge_lists(seq1, seq2):
        return [s for s in seq1 if s not in seq2] + seq2

    result = d1.copy()
    for k, v in d2.items():
        if k not in d1.keys():
            result[k] = v
        else:
            result[k] = merge_lists(d1[k], d2[k])
    return result
