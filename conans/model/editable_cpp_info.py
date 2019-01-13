# coding=utf-8
import ntpath
import os
import posixpath
import six
from collections import defaultdict
if six.PY2:
    from backports import configparser  # To use 'delimiters' in ConfigParser
else:
    import configparser

from conans.client.tools.files import load


class EditableCppInfo(object):
    WILDCARD = "*"
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs']

    def __init__(self, data, uses_namespace):
        self._data = data
        self._uses_namespace = uses_namespace

    @classmethod
    def load(cls, filepath, require_namespace):
        data = cls._loads(content=load(filepath), require_namespace=require_namespace)
        return EditableCppInfo(data, uses_namespace=require_namespace)

    @classmethod
    def loads(cls, content, require_namespace):
        data = cls._loads(content=content, require_namespace=require_namespace)
        return EditableCppInfo(data, uses_namespace=require_namespace)

    @classmethod
    def _loads(cls, content, require_namespace):
        """ Returns a dictionary containing information about paths for a CppInfo object: includes,
        libraries, resources, binaries,... """

        parser = configparser.ConfigParser(allow_no_value=True, delimiters=('#', ))
        parser.optionxform = str
        parser.read_string(content)

        if not require_namespace:
            ret = {k: [] for k in cls.cpp_info_dirs}
            for section in ret.keys():
                if section in parser:
                    ret[section] = parser[section]
            return ret
        else:
            ret = defaultdict(lambda: {k: [] for k in cls.cpp_info_dirs})
            for section in parser:
                if ':' in section:
                    namespace, key = section.split(':', 1)
                    if key in cls.cpp_info_dirs:
                        ret[namespace][key] = parser[section]
            return ret

    @staticmethod
    def _work_on_item(value, base_path, settings, options):
        value = value.replace('\\', '/')
        isabs = ntpath.isabs(value) or posixpath.isabs(value)
        if base_path and not isabs:
            value = os.path.abspath(os.path.join(base_path, value))
        value = os.path.normpath(value)
        value = value.format(settings=settings, options=options)
        return value

    def has_info_for(self, pck_name, use_wildcard=True):
        if self._uses_namespace:
            return pck_name in self._data or (use_wildcard and self.WILDCARD in self._data)
        else:
            return True

    def apply_to(self, pkg_name, cpp_info, base_path, settings=None, options=None,
                 use_wildcard=True):
        if self._uses_namespace:
            if pkg_name in self._data:
                data_to_apply = self._data[pkg_name]
            elif use_wildcard and self.WILDCARD in self._data:
                data_to_apply = self._data[self.WILDCARD]
            else:
                data_to_apply = {k: [] for k in self.cpp_info_dirs}
        else:
            data_to_apply = self._data

        for key, items in data_to_apply.items():
            setattr(cpp_info, key, [self._work_on_item(item, base_path, settings, options)
                                    for item in items])
