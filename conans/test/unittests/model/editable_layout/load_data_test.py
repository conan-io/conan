# coding=utf-8

import os
import shutil
import textwrap
import unittest

import six

from conans.errors import ConanException
from conans.model.editable_layout import EditableLayout
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.test_folder = temp_folder()
        self.layout_filepath = os.path.join(self.test_folder, "layout")
        self.editable_cpp_info = EditableLayout(self.layout_filepath)

    def tearDown(self):
        shutil.rmtree(self.test_folder)

    def test_field_error(self):
        content = textwrap.dedent("""
                            [includedrs]
                            something
                            """)
        save(self.layout_filepath, content)
        with six.assertRaisesRegex(self, ConanException, "Wrong cpp_info field 'includedrs' in layout"):
            _ = self.editable_cpp_info._load_data(ref=None, settings=None, options=None)
        content = textwrap.dedent("""
                            [*:includedrs]
                            something
                            """)
        save(self.layout_filepath, content)
        with six.assertRaisesRegex(self, ConanException, "Wrong cpp_info field 'includedrs' in layout"):
            _ = self.editable_cpp_info._load_data(ref=None, settings=None, options=None)

        content = textwrap.dedent("""
                            [*:includedirs]
                            something
                            """)
        save(self.layout_filepath, content)
        with six.assertRaisesRegex(self, ConanException, "Wrong package reference '\*' in layout file"):
            _ = self.editable_cpp_info._load_data(ref=None, settings=None, options=None)

        content = textwrap.dedent("""
                            [pkg/version@user/channel:revision:includedirs]
                            something
                            """)
        save(self.layout_filepath, content)
        with six.assertRaisesRegex(self, ConanException, "Wrong package reference "
                                     "'pkg/version@user/channel:revision' in layout file"):
            _ = self.editable_cpp_info._load_data(ref=None, settings=None, options=None)
