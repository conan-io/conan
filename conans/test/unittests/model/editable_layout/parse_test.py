# coding=utf-8

import os
import shutil
import textwrap
import unittest

from conans.client.conf import get_default_settings_yml
from conans.model.editable_layout import EditableLayout
from conans.model.options import Options, PackageOptions
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.test_folder = temp_folder()
        self.layout_filepath = os.path.join(self.test_folder, "layout")
        self.editable_cpp_info = EditableLayout(self.layout_filepath)

        self.settings = Settings.loads(get_default_settings_yml())
        self.options = Options(PackageOptions({"shared": [True, False]}))

    def tearDown(self):
        shutil.rmtree(self.test_folder)

    def test_render_basic(self):
        self.options.shared = True
        self.settings.build_type = "Debug"

        content = textwrap.dedent("""
            [includedirs]
            {% if options.shared %}
            path/to/shared/{{ settings.build_type }}
            {% else %}
            not/expected
            {% endif %}
            """)
        save(self.layout_filepath, content)

        data, folders = self.editable_cpp_info._load_data(ref=None, settings=self.settings,
                                                          options=self.options)
        self.assertEqual(data[None], {'includedirs': ["path/to/shared/Debug"]})

    def test_render_loop(self):
        self.settings.build_type = "Debug"

        content = textwrap.dedent("""
            [includedirs]
            {% for item in ["cmp1", "cmp2", "cmp3"] %}
            components\{{ item }}\include\{% if item != "cmp3" %}{{ settings.build_type }}{% endif %}
            {% endfor %}
            """)
        save(self.layout_filepath, content)

        data, folders = self.editable_cpp_info._load_data(ref=None, settings=self.settings,
                                                          options=self.options)
        self.assertEqual(data[None], {'includedirs': ["components/cmp1/include/Debug",
                                                      "components/cmp2/include/Debug",
                                                      "components/cmp3/include/"]})
