# coding=utf-8

import os
import textwrap
import unittest

import six

from conans.model.editable_cpp_info import EditableCppInfo
from conans.model.build_info import CppInfo

base_content = six.u(textwrap.dedent("""\
    [{namespace}includedirs]
    {path_prefix}dirs/includedirs

    [{namespace}libdirs]
    {path_prefix}dirs/libdirs

    [{namespace}resdirs]
    {path_prefix}dirs/resdirs

    #[{namespace}bindirs]
    #{path_prefix}dirs/bindirs

    """))


class ApplyEditableCppInfoTest(unittest.TestCase):
    content = '\n\n'.join([
        base_content.format(namespace="", path_prefix=""),
        base_content.format(namespace="*:", path_prefix="all/"),
        base_content.format(namespace="libA:", path_prefix="libA/")
    ])

    def test_require_no_namespace(self):
        editable_cpp_info = EditableCppInfo.loads(content=self.content, allow_wildcard=True)

        cpp_info = CppInfo(None)
        editable_cpp_info.apply_to('libA', cpp_info, settings=None, options=None)
        self.assertListEqual(cpp_info.includedirs, ['dirs/includedirs'])
        self.assertListEqual(cpp_info.libdirs, ['dirs/libdirs'])
        self.assertListEqual(cpp_info.resdirs, ['dirs/resdirs'])
        # The default defined by package_info() is maintained
        self.assertListEqual(cpp_info.bindirs, ['bin'])

    def test_require_namespace(self):
        editable_cpp_info = EditableCppInfo.loads(content=self.content, allow_wildcard=True)
        cpp_info = CppInfo(None)

        # Apply to 'libA' ==> existing one
        editable_cpp_info.apply_to('libA', cpp_info, settings=None, options=None)
        self.assertListEqual(cpp_info.includedirs, ['libA/dirs/includedirs', ])
        self.assertListEqual(cpp_info.libdirs, ['libA/dirs/libdirs', ])
        self.assertListEqual(cpp_info.resdirs, [os.path.normpath('libA/dirs/resdirs'), ])
        self.assertListEqual(cpp_info.bindirs, [])

        # Apply to non existing lib ==> uses wildcard ones
        editable_cpp_info.apply_to('libOther', cpp_info, settings=None, options=None)
        self.assertListEqual(cpp_info.includedirs, [os.path.normpath('all/dirs/includedirs'), ])
        self.assertListEqual(cpp_info.libdirs, [os.path.normpath('all/dirs/libdirs'), ])
        self.assertListEqual(cpp_info.resdirs, [os.path.normpath('all/dirs/resdirs'), ])
        self.assertListEqual(cpp_info.bindirs, [])

        # Apply to non existing lib ==> not found, and not wildcard allowed
        editable_cpp_info.apply_to('libOther', cpp_info, settings=None, options=None,
                                   use_wildcard=False)
        self.assertListEqual(cpp_info.includedirs, [])
        self.assertListEqual(cpp_info.libdirs, [])
        self.assertListEqual(cpp_info.resdirs, [])
        self.assertListEqual(cpp_info.bindirs, [])
