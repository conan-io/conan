# coding=utf-8

import textwrap
import os
import shutil
import unittest

from conans.errors import ConanException
from conans.model.editable_cpp_info import EditableCppInfo
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.test_folder = temp_folder()
        self.layout_filepath = os.path.join(self.test_folder, "layout")

    def tearDown(self):
        shutil.rmtree(self.test_folder)

    def field_error_test(self):
        content = textwrap.dedent("""
                            [includedrs]
                            something
                            """)
        save(self.layout_filepath, content)
        with self.assertRaisesRegexp(ConanException, "Wrong cpp_info field 'includedrs' in layout"):
            _ = EditableCppInfo.load(self.layout_filepath)
        content = textwrap.dedent("""
                            [*:includedrs]
                            something
                            """)
        save(self.layout_filepath, content)
        with self.assertRaisesRegexp(ConanException, "Wrong cpp_info field 'includedrs' in layout"):
            _ = EditableCppInfo.load(self.layout_filepath)

        content = textwrap.dedent("""
                            [*:includedirs]
                            something
                            """)
        save(self.layout_filepath, content)
        with self.assertRaisesRegexp(ConanException, "Wrong package reference '\*' in layout file"):
            _ = EditableCppInfo.load(self.layout_filepath)

        content = textwrap.dedent("""
                            [pkg/version@user/channel:revision:includedirs]
                            something
                            """)
        save(self.layout_filepath, content)
        with self.assertRaisesRegexp(ConanException, "Wrong package reference "
                                     "'pkg/version@user/channel:revision' in layout file"):
            _ = EditableCppInfo.load(self.layout_filepath)
