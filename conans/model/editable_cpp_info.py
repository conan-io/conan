# coding=utf-8
import os

from six.moves import configparser

from conans.errors import ConanException

CONAN_PACKAGE_LAYOUT_FILE = '.conan_layout'
DEFAULT_LAYOUT_FILE = "default"
LAYOUTS_FOLDER = 'layouts'


def get_editable_abs_path(layout, cwd, cache_folder):
    # Check the layout file exists, is correct, and get its abs-path
    name = layout or CONAN_PACKAGE_LAYOUT_FILE
    layout_abs_path = name if os.path.isabs(name) else os.path.normpath(os.path.join(cwd, name))
    cache_layout = layout or DEFAULT_LAYOUT_FILE
    cache_layout_path = os.path.join(cache_folder, LAYOUTS_FOLDER, cache_layout)

    if os.path.isfile(layout_abs_path):
        EditableCppInfo.load(layout_abs_path)  # Try if it loads ok
    elif os.path.isfile(cache_layout_path):
        layout_abs_path = cache_layout_path
        EditableCppInfo.load(cache_layout_path)
    elif layout:
        raise ConanException("Couldn't find layout file: %s" % layout)
    else:
        layout_abs_path = None  # No default layout exists
    return layout_abs_path


class EditableCppInfo(object):
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs']

    def __init__(self, data):
        self._data = data

    @staticmethod
    def load(filepath):
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

        return EditableCppInfo(data)

    @staticmethod
    def _work_on_item(value, settings, options):
        value = value.format(settings=settings, options=options)
        value = value.replace('\\', '/')
        return value

    def apply_to(self, pkg_name, cpp_info, settings=None, options=None):
        d = self._data
        data = d.get(pkg_name) or d.get(None) or {}

        if data:  # Invalidate previously existing dirs
            for info_dir in self.cpp_info_dirs:
                setattr(cpp_info, info_dir, [])
        try:
            for key, items in data.items():
                setattr(cpp_info, key, [self._work_on_item(item, settings, options)
                                        for item in items])
        except Exception as e:
            raise ConanException("Error applying layout in '%s': %s" % (pkg_name, str(e)))
