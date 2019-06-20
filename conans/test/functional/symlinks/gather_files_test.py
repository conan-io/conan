# coding=utf-8

import os
import unittest

import six

from conans.client.tools import environment_append
from conans.client.tools.files import chdir
from conans.errors import ConanException
from conans.model.manifest import gather_files
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save, save_files


class GatherFilesTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp_folder = temp_folder()
        with chdir(self.tmp_folder):
            # Create some files
            save("linked_file", "")
            os.makedirs("linked_folder")
            ori_files_dir = os.path.join(self.tmp_folder, "ori")
            save_files(ori_files_dir, {"file1": "",
                                       "folder/file2": ""})
            # And symlinks pointing outside
            os.symlink(os.path.join(self.tmp_folder, "linked_folder"),
                       os.path.join(ori_files_dir, "out_folder"))
            os.symlink(os.path.join(self.tmp_folder, "linked_file"),
                       os.path.join(ori_files_dir, "out_file"))

    def test_basic_behavior(self):
        output = TestBufferConanOutput()
        gathered_files = gather_files(os.path.join(self.tmp_folder, "ori"), output)
        self.assertListEqual(sorted(gathered_files.files.keys()),
                             ['file1', 'folder/file2', 'out_file'])
        self.assertListEqual(sorted(gathered_files.symlinks.keys()), ['out_folder'])

    def test_error_broken_file(self):
        os.unlink(os.path.join(self.tmp_folder, 'linked_file'))

        output = TestBufferConanOutput()
        with six.assertRaisesRegex(self, ConanException, "The file is a broken symlink"):
            gather_files(os.path.join(self.tmp_folder, "ori"), output)

    def test_error_broken_directory(self):
        os.rmdir(os.path.join(self.tmp_folder, 'linked_folder'))

        output = TestBufferConanOutput()
        with six.assertRaisesRegex(self, ConanException, "The file is a broken symlink"):
            gather_files(os.path.join(self.tmp_folder, "ori"), output)

    def test_warn_broken_file(self):
        os.unlink(os.path.join(self.tmp_folder, 'linked_file'))

        output = TestBufferConanOutput()
        with environment_append({"CONAN_SKIP_BROKEN_SYMLINKS_CHECK": "True"}):
            gathered_files = gather_files(os.path.join(self.tmp_folder, "ori"), output)
        self.assertIn("WARN: Broken symlink", output)
        self.assertListEqual(sorted(gathered_files.files.keys()),
                             ['file1', 'folder/file2',])
        self.assertListEqual(sorted(gathered_files.symlinks.keys()), ['out_folder'])

    def test_warn_broken_directory(self):
        os.rmdir(os.path.join(self.tmp_folder, 'linked_folder'))

        output = TestBufferConanOutput()
        with environment_append({"CONAN_SKIP_BROKEN_SYMLINKS_CHECK": "True"}):
            gathered_files = gather_files(os.path.join(self.tmp_folder, "ori"), output)
        self.assertIn("WARN: Broken symlink", output)
        self.assertListEqual(sorted(gathered_files.files.keys()),
                             ['file1', 'folder/file2', 'out_file'])
        self.assertListEqual(sorted(gathered_files.symlinks.keys()), [])
