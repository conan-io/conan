# coding=utf-8

import os
import unittest

from conans.client.cmd.uploader import _compress_files
from conans.client.tools import environment_append
from conans.client.tools.files import chdir
from conans.model.manifest import gather_files
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import tar_extract, save, save_files


class TarExtractTestSuite(unittest.TestCase):

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

        with environment_append({"CONAN_SKIP_BROKEN_SYMLINKS_CHECK": "True"}):
            gathered_files = gather_files(ori_files_dir, output=None)

        # Create a tar.gz file with the above files
        self.tgz_file = _compress_files(gathered_files, "file.tar.gz", self.tmp_folder, output=None)

    def test_warn_outside_symlink(self):
        output = TestBufferConanOutput()
        dst_folder = temp_folder()
        with open(self.tgz_file, 'rb') as file_handler:
            tar_extract(file_handler, dst_folder, output=output)

        self.assertIn("WARN: File 'out_folder' inside the tar is a symlink pointing outside"
                      " the tar, it will be skipped", output)
        self.assertIn("WARN: File 'out_file' inside the tar is a symlink pointing outside"
                      " the tar, it will be skipped", output)

        self.assertListEqual(sorted(os.listdir(dst_folder)), ['file1', 'folder'])
