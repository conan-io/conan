# coding=utf-8

import os
import textwrap
import unittest
from collections import namedtuple

import six

from conans.model.editable_cpp_info import EditableCppInfo

base_content = six.u(textwrap.dedent("""\
    [{namespace}includedirs]
    {path_prefix}dirs/includedirs

    [{namespace}libdirs]
    {path_prefix}dirs/libdirs

    [{namespace}resdirs]
    {path_prefix}dirs/resdirs

    #[{namespace}bindirs]
    #{path_prefix}dirs/bindirs

    [{namespace}extradirs]
    {path_prefix}dirs/extradirs
    """))


class ApplyEditableCppInfoTest(unittest.TestCase):
    content = '\n\n'.join([
        base_content.format(namespace="", path_prefix=""),
        base_content.format(namespace="*:", path_prefix="all/"),
        base_content.format(namespace="libA:", path_prefix="libA/")
    ])

    def test_require_no_namespace(self):
        editable_cpp_info = EditableCppInfo.loads(content=self.content, require_namespace=False)

        cpp_info = namedtuple('_', EditableCppInfo.cpp_info_dirs)
        editable_cpp_info.apply_to('libA', cpp_info, base_path=None, settings=None, options=None)
        self.assertTrue(editable_cpp_info.has_info_for('any-thing'))
        self.assertListEqual(cpp_info.includedirs, [os.path.normpath('dirs/includedirs'), ])
        self.assertListEqual(cpp_info.libdirs, [os.path.normpath('dirs/libdirs'), ])
        self.assertListEqual(cpp_info.resdirs, [os.path.normpath('dirs/resdirs'), ])
        self.assertListEqual(cpp_info.bindirs, [])

    def test_require_namespace(self):
        editable_cpp_info = EditableCppInfo.loads(content=self.content, require_namespace=True)
        self.assertTrue(editable_cpp_info.has_info_for('libA', use_wildcard=True))
        self.assertTrue(editable_cpp_info.has_info_for('libA', use_wildcard=False))
        self.assertTrue(editable_cpp_info.has_info_for('libOther', use_wildcard=True))
        self.assertFalse(editable_cpp_info.has_info_for('libOther', use_wildcard=False))

        cpp_info = namedtuple('_', EditableCppInfo.cpp_info_dirs)

        # Apply to 'libA' ==> existing one
        editable_cpp_info.apply_to('libA', cpp_info, base_path=None, settings=None, options=None)
        self.assertListEqual(cpp_info.includedirs, [os.path.normpath('libA/dirs/includedirs'), ])
        self.assertListEqual(cpp_info.libdirs, [os.path.normpath('libA/dirs/libdirs'), ])
        self.assertListEqual(cpp_info.resdirs, [os.path.normpath('libA/dirs/resdirs'), ])
        self.assertListEqual(cpp_info.bindirs, [])

        # Apply to non existing lib ==> uses wildcard ones
        editable_cpp_info.apply_to('libOther', cpp_info, base_path=None, settings=None, options=None)
        self.assertListEqual(cpp_info.includedirs, [os.path.normpath('all/dirs/includedirs'), ])
        self.assertListEqual(cpp_info.libdirs, [os.path.normpath('all/dirs/libdirs'), ])
        self.assertListEqual(cpp_info.resdirs, [os.path.normpath('all/dirs/resdirs'), ])
        self.assertListEqual(cpp_info.bindirs, [])

        # Apply to non existing lib ==> not found, and not wildcard allowed
        editable_cpp_info.apply_to('libOther', cpp_info, base_path=None, settings=None, options=None,
                                   use_wildcard=False)
        self.assertListEqual(cpp_info.includedirs, [])
        self.assertListEqual(cpp_info.libdirs, [])
        self.assertListEqual(cpp_info.resdirs, [])
        self.assertListEqual(cpp_info.bindirs, [])
