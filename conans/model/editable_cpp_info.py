# coding=utf-8
import os
from collections import OrderedDict
import tempfile
from io import StringIO
from six.moves import configparser
from conans.util.files import load
from conans.util.jinja import render_layout_file

from conans.errors import ConanException
from conans.model.ref import ConanFileReference

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


class EditableCppInfo(object):
    cpp_info_dirs = ['includedirs', 'libdirs', 'resdirs', 'bindirs', 'builddirs', 'srcdirs']

    def __init__(self, filepath):
        self._filepath = filepath

    def _parse_layout_file(self, ref, settings, options):
        content = load(self._filepath)
        try:
            content = render_layout_file(content, ref=ref, settings=settings, options=options)

            parser = configparser.ConfigParser(allow_no_value=True)
            parser.optionxform = str
            parser.readfp(StringIO(content))
        except (configparser.Error, ConanException) as e:
            raise ConanException("Error parsing layout file '%s' (for reference '%s')\n%s" %
                                 (self._filepath, str(ref), str(e)))

        return parser

    def _load_data(self, ref, settings, options):
        parser = self._parse_layout_file(ref, settings, options)

        # Build a convenient data structure
        data = OrderedDict()
        for section in parser.sections():
            reference, cpp_info_dir = section.rsplit(":", 1) if ':' in section else (None, section)
            if cpp_info_dir not in EditableCppInfo.cpp_info_dirs:
                raise ConanException("Wrong cpp_info field '%s' in layout file: %s"
                                     % (cpp_info_dir, self._filepath))
            if reference:
                try:
                    r = ConanFileReference.loads(reference)
                    if r.revision:
                        raise ConanException
                except ConanException:
                    raise ConanException("Wrong package reference '%s' in layout file: %s"
                                         % (reference, self._filepath))
            data.setdefault(reference, {})[cpp_info_dir] = [k for k, _ in parser.items(section)]
        return data

    def apply_to(self, ref, cpp_info, settings=None, options=None):
        data = self._load_data(ref, settings=settings, options=options)

        # Apply the data to the cpp_info
        data = data.get(str(ref)) or data.get(None) or {}

        if data:  # Invalidate previously existing dirs
            for info_dir in self.cpp_info_dirs:
                setattr(cpp_info, info_dir, [])
        for key, items in data.items():
            setattr(cpp_info, key, items)
