# coding=utf-8

from six.moves import configparser

from conans.errors import ConanException


class EditableCppInfo(object):
    WILDCARD = "*"
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs']

    def __init__(self, data):
        self._data = data

    @staticmethod
    def load(filepath, allow_package_name=False):
        parser = configparser.ConfigParser(allow_no_value=True)
        parser.optionxform = str
        try:
            parser.read(filepath)
        except configparser.Error:
            raise ConanException("Error parsing layout file: %s" % filepath)
        data = {}
        for section in parser.sections():
            pkg, key = section.split(":", 1) if ':' in section else (None, section)
            if key not in EditableCppInfo.cpp_info_dirs:
                raise ConanException("Wrong cpp_info field '%s' in layout file: %s"
                                     % (key, filepath))
            data.setdefault(pkg, {})[key] = [k for k, _ in parser.items(section)]

        if not allow_package_name and [d for d in data if d]:
            raise ConanException("Repository layout file doesn't allow patterns: %s" % filepath)
        else:
            if data.get(None) and data.get(EditableCppInfo.WILDCARD):
                raise ConanException("Using both generic '[includedirs]' "
                                     "and wildcard '[*:includedirs]' syntax. Use just one in: %s"
                                     % filepath)
        return EditableCppInfo(data)

    @staticmethod
    def _work_on_item(value, settings, options):
        value = value.format(settings=settings, options=options)
        value = value.replace('\\', '/')
        return value

    def apply_to(self, pkg_name, cpp_info, settings=None, options=None):
        d = self._data
        data = d.get(pkg_name) or d.get(self.WILDCARD) or d.get(None) or {}

        try:
            for key, items in data.items():
                setattr(cpp_info, key, [self._work_on_item(item, settings, options)
                                        for item in items])
        except Exception as e:
            raise ConanException("Error applying layout in '%s': %s" % (pkg_name, str(e)))
