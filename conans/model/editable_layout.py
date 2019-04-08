# coding=utf-8
import os
from collections import OrderedDict

import six
from six.moves import configparser

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.files import load
from conans.util.templates import render_layout_file

DEFAULT_LAYOUT_FILE = "default"
LAYOUTS_FOLDER = 'layouts'


def get_editable_abs_path(path, cwd, cache_folder):
    # Check the layout file exists, is correct, and get its abs-path
    if path:
        layout_abs_path = os.path.normpath(os.path.join(cwd, path))
        if not os.path.isfile(layout_abs_path):
            layout_abs_path = os.path.join(cache_folder, LAYOUTS_FOLDER, path)
        if not os.path.isfile(layout_abs_path):
            raise ConanException("Couldn't find layout file: %s" % path)
        return layout_abs_path

    # Default only in cache
    layout_default_path = os.path.join(cache_folder, LAYOUTS_FOLDER, DEFAULT_LAYOUT_FILE)
    if os.path.isfile(layout_default_path):
        return layout_default_path


class EditableLayout(object):
    BUILD_FOLDER = "build_folder"
    SOURCE_FOLDER = "source_folder"
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs', 'builddirs', 'srcdirs']
    folders = [BUILD_FOLDER, SOURCE_FOLDER]

    def __init__(self, filepath):
        self._filepath = filepath

    def folder(self, ref, name, settings, options):
        _, folders = self._load_data(ref, settings=settings, options=options)
        try:
            path = folders.get(str(ref)) or folders.get(None) or {}
            return path[name]
        except KeyError:
            return None

    @staticmethod
    def _work_on_item(value):
        value = value.replace('\\', '/')
        return value

    def _parse_layout_file(self, ref, settings, options):
        content = load(self._filepath)
        try:
            content = render_layout_file(content, ref=ref, settings=settings, options=options)

            parser = configparser.ConfigParser(allow_no_value=True)
            parser.optionxform = str
            if six.PY3:
                parser.read_string(content)
            else:
                parser.readfp(six.StringIO(content))
        except (configparser.Error, ConanException) as e:
            raise ConanException("Error parsing layout file '%s' (for reference '%s')\n%s" %
                                 (self._filepath, str(ref), str(e)))

        return parser

    def _load_data(self, ref, settings, options):
        parser = self._parse_layout_file(ref, settings, options)

        # Build a convenient data structure
        data = OrderedDict()
        folders = {}
        for section in parser.sections():
            reference, section_name = section.rsplit(":", 1) if ':' in section else (None, section)

            if section_name in EditableLayout.folders:
                items = [k for k, _ in parser.items(section)] or [""]
                if len(items) > 1:
                    raise ConanException("'%s' with more than one value in layout file: %s"
                                         % (section_name, self._filepath))
                folders.setdefault(reference, {})[section_name] = self._work_on_item(items[0])
                continue

            if section_name not in EditableLayout.cpp_info_dirs:
                raise ConanException("Wrong cpp_info field '%s' in layout file: %s"
                                     % (section_name, self._filepath))
            if reference:
                try:
                    r = ConanFileReference.loads(reference, validate=True)
                    if r.revision:
                        raise ConanException("Don't provide revision in Editable layouts")
                except ConanException:
                    raise ConanException("Wrong package reference '%s' in layout file: %s"
                                         % (reference, self._filepath))
            data.setdefault(reference, {})[section_name] =\
                [self._work_on_item(k) for k, _ in parser.items(section)]
        return data, folders

    def apply_to(self, ref, cpp_info, settings=None, options=None):
        data, _ = self._load_data(ref, settings=settings, options=options)

        # Apply the data to the cpp_info
        data = data.get(str(ref)) or data.get(None) or {}

        try:
            for key, items in data.items():
                setattr(cpp_info, key, items)
        except Exception as e:
            raise ConanException("Error applying layout in '%s': %s" % (str(ref), str(e)))
