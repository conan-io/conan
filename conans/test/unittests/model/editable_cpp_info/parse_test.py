# coding=utf-8

import textwrap
import os
import shutil
import unittest

import six

from conans.model.editable_cpp_info import EditableCppInfo
from conans.test.utils.test_files import temp_folder
from conans.util.files import save

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


class NoNamespaceFileTest(unittest.TestCase):
    content = '\n\n'.join([
        base_content.format(namespace="", path_prefix=""),
        base_content.format(namespace="*:", path_prefix="all/"),
        base_content.format(namespace="libA:", path_prefix="libA/")
    ])

    def setUp(self):
        self.test_folder = temp_folder()
        self.layout_filepath = os.path.join(self.test_folder, "layout")

    def test_read_empty_no_namespace(self):
        save(self.layout_filepath, base_content.format(namespace="libA:", path_prefix="libA/"))
        editable_cpp_info = EditableCppInfo.load(filepath=self.layout_filepath,
                                                 require_namespace=False)
        self.assertFalse(editable_cpp_info._uses_namespace)

        data = editable_cpp_info._data
        self.assertListEqual(sorted(data.keys()), sorted(EditableCppInfo.cpp_info_dirs))
        self.assertFalse(len(data['includedirs']))
        self.assertFalse(len(data['libdirs']))
        self.assertFalse(len(data['resdirs']))
        self.assertFalse(len(data['bindirs']))

    def test_read_empty_namespace(self):
        save(self.layout_filepath, base_content.format(namespace="", path_prefix=""))
        editable_cpp_info = EditableCppInfo.load(self.layout_filepath, require_namespace=True)
        self.assertTrue(editable_cpp_info._uses_namespace)
        self.assertFalse(len(editable_cpp_info._data.keys()))

    def test_no_namespace(self):
        save(self.layout_filepath, self.content)
        editable_cpp_info = EditableCppInfo.load(self.layout_filepath, require_namespace=False)
        self.assertFalse(editable_cpp_info._uses_namespace)

        data = editable_cpp_info._data
        self.assertListEqual(sorted(data.keys()), sorted(EditableCppInfo.cpp_info_dirs))
        self.assertListEqual(list(data['includedirs']), ['dirs/includedirs', ])
        self.assertListEqual(list(data['libdirs']), ['dirs/libdirs', ])
        self.assertListEqual(list(data['resdirs']), ['dirs/resdirs', ])
        self.assertListEqual(list(data['bindirs']), [])

    def test_namespace(self):
        save(self.layout_filepath, self.content)
        editable_cpp_info = EditableCppInfo.load(self.layout_filepath, require_namespace=True)
        self.assertTrue(editable_cpp_info._uses_namespace)

        self.assertListEqual(sorted(editable_cpp_info._data.keys()), sorted(['*', 'libA', ]))

        # Check '*'
        data = editable_cpp_info._data['*']
        self.assertListEqual(sorted(data.keys()),
                             sorted(EditableCppInfo.cpp_info_dirs))
        self.assertListEqual(list(data['includedirs']), ['all/dirs/includedirs', ])
        self.assertListEqual(list(data['libdirs']), ['all/dirs/libdirs', ])
        self.assertListEqual(list(data['resdirs']), ['all/dirs/resdirs', ])
        self.assertListEqual(list(data['bindirs']), [])

        # Check 'libA'
        data = editable_cpp_info._data['libA']
        self.assertListEqual(sorted(data.keys()),
                             sorted(EditableCppInfo.cpp_info_dirs))
        self.assertListEqual(list(data['includedirs']), ['libA/dirs/includedirs', ])
        self.assertListEqual(list(data['libdirs']), ['libA/dirs/libdirs', ])
        self.assertListEqual(list(data['resdirs']), ['libA/dirs/resdirs', ])
        self.assertListEqual(list(data['bindirs']), [])

    def tearDown(self):
        shutil.rmtree(self.test_folder)
