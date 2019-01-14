# coding=utf-8

import six

from conans.errors import ConanException
from conans.client.tools.files import load

if six.PY2:
    from backports import configparser  # To use 'delimiters' in ConfigParser
else:
    import configparser


class EditableCppInfo(object):
    WILDCARD = "*"
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs']

    def __init__(self, data):
        self._data = data

    @staticmethod
    def load(filepath, allow_package_name=False):
        return EditableCppInfo.loads(load(filepath), allow_package_name=allow_package_name)

    @classmethod
    def loads(cls, content, allow_package_name=False):
        data = cls._loads(content)
        if not allow_package_name and [d for d in data if d]:
            raise ConanException("Repository layout file doesn't allow patterns")
        else:
            if data.get(None) and data.get(cls.WILDCARD):
                raise ConanException("Using both generic '[includedirs]' "
                                     "and wildcard '[*:includedirs]' syntax. Use just one")
        return EditableCppInfo(data)

    @classmethod
    def _loads(cls, content):
        """ Returns a dictionary containing information about paths for a CppInfo object: includes,
        libraries, resources, binaries,... """

        parser = configparser.ConfigParser(allow_no_value=True, delimiters=('#', ))
        parser.optionxform = str
        try:
            content = content.decode("utf-8")
        except:
            pass
        parser.read_string(content)

        ret = {}
        for section in parser.sections():
            pkg, key = section.split(":", 1) if ':' in section else (None, section)
            if key not in cls.cpp_info_dirs:
                raise ConanException("Wrong cpp_info field: %s" % key)
            ret.setdefault(pkg, {})[key] = parser[section]
        return ret

    @staticmethod
    def _work_on_item(value, settings, options):
        value = value.format(settings=settings, options=options)
        value = value.replace('\\', '/')
        return value

    def apply_to(self, pkg_name, cpp_info, settings=None, options=None):
        d = self._data
        data = d.get(pkg_name) or d.get(self.WILDCARD) or d.get(None) or {}

        for key, items in data.items():
            setattr(cpp_info, key, [self._work_on_item(item, settings, options)
                                    for item in items])
