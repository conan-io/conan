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
        EditableLayout.load(layout_abs_path)  # Try if it loads ok
        return layout_abs_path

    # Default only in cache
    layout_abs_path = os.path.join(cache_folder, LAYOUTS_FOLDER, DEFAULT_LAYOUT_FILE)
    if os.path.isfile(layout_abs_path):
        EditableLayout.load(layout_abs_path)
        return layout_abs_path


class EditableLayout(object):
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs', 'builddirs', 'srcdirs']
    folders = ['build_folder', 'source_folder']

    def __init__(self, data, folders):
        self._data = data
        self._folders = folders

    def folder(self, ref, name, settings, options):
        try:
            path = self._folders.get(str(ref)) or self._folders.get(None) or {}
            path = path[name]
        except KeyError:
            return None
        try:
            return self._work_on_item(path, settings, options)
        except Exception as e:
            raise ConanException("Error getting fHolder '%s' from layout: %s" % (str(name), str(e)))

    @staticmethod
    def load(filepath):
        parser = configparser.ConfigParser(allow_no_value=True)
        parser.optionxform = str
        try:
            parser.read(filepath)
        except configparser.Error as e:
            raise ConanException("Error parsing layout file: %s\n%s" % (filepath, str(e)))
        data = OrderedDict()
        folders = {}
        for section in parser.sections():
            ref, section_name = section.rsplit(":", 1) if ':' in section else (None, section)
            if section_name in EditableLayout.folders:
                items = [k for k, _ in parser.items(section)] or [""]
                if len(items) > 1:
                    raise ConanException("'%s' with more than one value in layout file: %s"
                                         % (section_name, filepath))
                folders.setdefault(ref, {})[section_name] = items[0]
                continue
            if section_name not in EditableLayout.cpp_info_dirs:
                raise ConanException("Wrong cpp_info field '%s' in layout file: %s"
                                     % (section_name, filepath))
            if ref:
                try:
                    r = ConanFileReference.loads(ref, validate=True)
                    if r.revision:
                        raise ConanException("Don't provide revision in Editable layouts")
                except ConanException:
                    raise ConanException("Wrong package reference '%s' in layout file: %s"
                                         % (ref, filepath))
            data.setdefault(ref, {})[section_name] = [k for k, _ in parser.items(section)]

        return EditableLayout(data, folders)

    @staticmethod
    def _work_on_item(value, settings, options):
        value = value.format(settings=settings, options=options)
        value = value.replace('\\', '/')
        return value

    def apply_to(self, ref, cpp_info, settings=None, options=None):
        d = self._data
        data = d.get(str(ref)) or d.get(None) or {}

        try:
            for key, items in data.items():
                setattr(cpp_info, key, [self._work_on_item(item, settings, options)
                                        for item in items])
        except Exception as e:
            raise ConanException("Error applying layout in '%s': %s" % (str(ref), str(e)))
