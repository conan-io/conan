# coding=utf-8

import os
import platform
import unittest

from parameterized import parameterized

from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save, copy_symlink


@unittest.skipUnless(platform.system() != "Windows", "Symlinks not handled for Windows")
class CopySymlinkTestSuite(unittest.TestCase):

    @parameterized.expand([(False, ), (True, )])
    def test_symlink_inside(self, file_exists):
        ori_folder = temp_folder()
        linked_file = os.path.join(ori_folder, "file")
        if file_exists:
            save(linked_file, "")
        ptr_source = os.path.join(ori_folder, "link_file")
        os.symlink(linked_file, ptr_source)

        output = TestBufferConanOutput()
        dst_folder = temp_folder()
        copy_symlink(ptr_source, ori_folder, dst_folder, output=output)

        self.assertEqual("", str(output))
        # The link exists, but the file has not been copied yet
        self.assertTrue(os.path.islink(os.path.join(dst_folder, "link_file")))
        self.assertFalse(os.path.exists(os.path.join(dst_folder, "link_file")))

    @parameterized.expand([(False, ), (True, )])
    def test_symlink_inside_with_dot(self, file_exists):
        ori_folder = temp_folder()
        linked_file = os.path.join(ori_folder, ".file")
        if file_exists:
            save(linked_file, "")
        ptr_source = os.path.join(ori_folder, ".link_file")
        os.symlink(linked_file, ptr_source)

        output = TestBufferConanOutput()
        dst_folder = temp_folder()
        copy_symlink(ptr_source, ori_folder, dst_folder, output=output)

        self.assertEqual("", str(output))
        # The link exists, but the file has not been copied yet
        self.assertTrue(os.path.islink(os.path.join(dst_folder, ".link_file")))
        self.assertFalse(os.path.exists(os.path.join(dst_folder, ".link_file")))

    @parameterized.expand([(False,), (True,)])
    def test_symlink_outside(self, file_exists):
        base_folder = temp_folder()
        linked_file = os.path.join(base_folder, "file")
        if file_exists:
            save(linked_file, "")

        ori_folder = os.path.join(base_folder, "ori")
        os.makedirs(ori_folder)
        ptr_source = os.path.join(ori_folder, "link_file")
        os.symlink(linked_file, ptr_source)

        output = TestBufferConanOutput()
        dst_folder = temp_folder()
        copy_symlink(ptr_source, ori_folder, dst_folder, output=output)

        self.assertIn("WARN: Symbolic link '{}' is pointing to '{}' outside the source folder"
                      " and won't be copied".format(ptr_source, ori_folder), str(output))
        # The link doesn't exists
        self.assertFalse(os.path.islink(os.path.join(dst_folder, "link_file")))
