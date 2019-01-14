# coding=utf-8

import textwrap
import unittest

from conans.model.editable_cpp_info import EditableCppInfo
from conans.model.build_info import CppInfo

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

    def test_require_no_namespace(self):
        content = base_content.format(namespace="", path_prefix="")
        editable_cpp_info = EditableCppInfo.loads(content=content, allow_package_name=False)
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
        editable_cpp_info = EditableCppInfo.loads(content=content, allow_package_name=True)
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
