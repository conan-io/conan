# coding=utf-8


import os
import shutil
import textwrap
import unittest

from conans.model.editable_cpp_info import EditableCppInfo
from conans.model.build_info import CppInfo
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


base_content = textwrap.dedent("""\
    [{namespace}includedirs]
    {path_prefix}dirs/includedirs

    [{namespace}libdirs]
    {path_prefix}dirs/libdirs

    [{namespace}resdirs]
    {path_prefix}dirs/resdirs

    #[{namespace}bindirs]
    #{path_prefix}dirs/bindirs

    """)


class ApplyEditableCppInfoTest(unittest.TestCase):

    def setUp(self):
        self.test_folder = temp_folder()
        self.layout_filepath = os.path.join(self.test_folder, "layout")

    def tearDown(self):
        shutil.rmtree(self.test_folder)

    def test_require_no_namespace(self):
        content = base_content.format(namespace="", path_prefix="")
        save(self.layout_filepath, content)
        editable_cpp_info = EditableCppInfo.load(self.layout_filepath, allow_package_name=False)
        cpp_info = CppInfo(None)
        editable_cpp_info.apply_to('libA', cpp_info, settings=None, options=None)
        self.assertListEqual(cpp_info.includedirs, ['dirs/includedirs'])
        self.assertListEqual(cpp_info.libdirs, ['dirs/libdirs'])
        self.assertListEqual(cpp_info.resdirs, ['dirs/resdirs'])
        # The default defined by package_info() is maintained
        self.assertListEqual(cpp_info.bindirs, ['bin'])

    def test_require_namespace(self):
        content = '\n\n'.join([
            base_content.format(namespace="", path_prefix=""),
            base_content.format(namespace="libA:", path_prefix="libA/")
            ])
        save(self.layout_filepath, content)
        editable_cpp_info = EditableCppInfo.load(self.layout_filepath, allow_package_name=True)
        cpp_info = CppInfo(None)
        editable_cpp_info.apply_to('libA', cpp_info, settings=None, options=None)
        self.assertListEqual(cpp_info.includedirs, ['libA/dirs/includedirs'])
        self.assertListEqual(cpp_info.libdirs, ['libA/dirs/libdirs'])
        self.assertListEqual(cpp_info.resdirs, ['libA/dirs/resdirs'])
        # The default defined by package_info() is maintained
        self.assertListEqual(cpp_info.bindirs, ['bin'])

        cpp_info = CppInfo(None)
        editable_cpp_info.apply_to('other', cpp_info, settings=None, options=None)
        self.assertListEqual(cpp_info.includedirs, ['dirs/includedirs'])
        self.assertListEqual(cpp_info.libdirs, ['dirs/libdirs'])
        self.assertListEqual(cpp_info.resdirs, ['dirs/resdirs'])
        # The default defined by package_info() is maintained
        self.assertListEqual(cpp_info.bindirs, ['bin'])
