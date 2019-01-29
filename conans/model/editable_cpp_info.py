# coding=utf-8
import os
from collections import OrderedDict

from six.moves import configparser

from conans.errors import ConanException
from conans.model.ref import ConanFileReference

DEFAULT_LAYOUT_FILE = "default"
LAYOUTS_FOLDER = 'layouts'


def get_editable_abs_path(path, cwd, cache_folder):
    # Check the layout file exists, is correct, and get its abs-path
    if path:
        layout_abs_path = path if os.path.isabs(path) else os.path.normpath(os.path.join(cwd, path))
        if not os.path.isfile(layout_abs_path):
            layout_abs_path = os.path.join(cache_folder, LAYOUTS_FOLDER, path)
        if not os.path.isfile(layout_abs_path):
            raise ConanException("Couldn't find layout file: %s" % path)
        EditableCppInfo.load(layout_abs_path)  # Try if it loads ok
        return layout_abs_path

    # Default only in cache
    layout_abs_path = os.path.join(cache_folder, LAYOUTS_FOLDER, DEFAULT_LAYOUT_FILE)
    if os.path.isfile(layout_abs_path):
        EditableCppInfo.load(layout_abs_path)
        return layout_abs_path


class EditableCppInfo(object):
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs', 'builddirs', 'srcdirs']

    def __init__(self, data):
        self._data = data

    @staticmethod
    def load(filepath):
        parser = configparser.ConfigParser(allow_no_value=True)
        parser.optionxform = str
        try:
            parser.read(filepath)
        except configparser.Error as e:
            raise ConanException("Error parsing layout file: %s\n%s" % (filepath, str(e)))
        data = OrderedDict()
        for section in parser.sections():
            ref, cpp_info_dir = section.rsplit(":", 1) if ':' in section else (None, section)
            if cpp_info_dir not in EditableCppInfo.cpp_info_dirs:
                raise ConanException("Wrong cpp_info field '%s' in layout file: %s"
                                     % (cpp_info_dir, filepath))
            if ref:
                try:
                    r = ConanFileReference.loads(ref)
                    if r.revision:
                        raise ConanException
                except ConanException:
                    raise ConanException("Wrong package reference '%s' in layout file: %s"
                                         % (ref, filepath))
            data.setdefault(ref, {})[cpp_info_dir] = [k for k, _ in parser.items(section)]

        return EditableCppInfo(data)

    @staticmethod
    def _work_on_item(value, settings, options):
        value = value.format(settings=settings, options=options)
        value = value.replace('\\', '/')
        return value

    def apply_to(self, ref, cpp_info, settings=None, options=None):
        d = self._data
        data = d.get(str(ref)) or d.get(None) or {}

        if data:  # Invalidate previously existing dirs
            for info_dir in self.cpp_info_dirs:
                setattr(cpp_info, info_dir, [])
        try:
            for key, items in data.items():
                setattr(cpp_info, key, [self._work_on_item(item, settings, options)
                                        for item in items])
        except Exception as e:
            raise ConanException("Error applying layout in '%s': %s" % (str(ref), str(e)))
