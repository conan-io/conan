# coding=utf-8
import configparser
import ntpath
import os
import posixpath
import re

import six


class EditableCppInfo(object):
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs']

    def __init__(self, data):
        self._data = data

    @classmethod
    def create(cls, filepath_or_content, *args, **kwargs):
        _parse_func = cls.parse_file if os.path.exists(filepath_or_content) else cls.parse_content
        data = _parse_func(filepath_or_content, *args, **kwargs)
        return EditableCppInfo(data)

    @classmethod
    def parse_file(cls, filepath, base_path, settings=None, options=None):
        with open(filepath, 'r') as f:
            return cls.parse_content(content=six.u(f.read()), base_path=base_path,
                                     settings=settings, options=options)

    @classmethod
    def parse_content(cls, content, base_path, settings=None, options=None):
        """ Returns a dictionary containing information about paths for a CppInfo object: includes,
        libraries, resources, binaries,... """
        ret = {k: [] for k in cls.cpp_info_dirs}

        def _work_on_value(value, base_path_, settings_, options_):
            value = re.sub(r'\\\\+', r'\\', value)
            value = value.replace('\\', '/')
            isabs = ntpath.isabs(value) or posixpath.isabs(value)
            if base_path_ and not isabs:
                value = os.path.abspath(os.path.join(base_path_, value))
            value = os.path.normpath(value)
            value = value.format(settings=settings_, options=options_)
            return value

        parser = configparser.ConfigParser(allow_no_value=True, delimiters=('#', ))
        parser.optionxform = str
        parser.read_string(content)
        for section in ret.keys():
            if section in parser:
                ret[section] = [_work_on_value(value, base_path, settings, options)
                                for value in parser[section]]
        return ret

    def apply_to(self, cpp_info):
        for key, items in self._data.items():
            setattr(cpp_info, key, items)
        return cpp_info
