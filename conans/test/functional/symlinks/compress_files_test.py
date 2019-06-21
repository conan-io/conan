# coding=utf-8

import os
import platform
import unittest

import six

from conans.client.cmd.uploader import _compress_files
from conans.client.tools import environment_append
from conans.client.tools.files import chdir
from conans.model.manifest import gather_files
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save, save_files


@unittest.skipUnless(platform.system() != "Windows", "Symlinks not handled for Windows")
class CompressFilesTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp_folder = temp_folder()
        with chdir(self.tmp_folder):
            # Create some files
            save("linked_file", "")
            os.makedirs("linked_folder")
            ori_files_dir = os.path.join(self.tmp_folder, "ori")
            save_files(ori_files_dir, {"file1": "",
                                       "folder/file2": "",
                                       ".file1": "",
                                       ".folder/file2": ""})
            # And symlinks pointing outside
            self.out_folder = os.path.join(ori_files_dir, "out_folder")
            os.symlink(os.path.join(self.tmp_folder, "linked_folder"), self.out_folder)
            self.out_file = os.path.join(ori_files_dir, "out_file")
            os.symlink(os.path.join(self.tmp_folder, "linked_file"), self.out_file)

            # And some pointing inside
            self.in_folder = os.path.join(ori_files_dir, ".in_folder")
            os.symlink(os.path.join(ori_files_dir, ".folder"), self.in_folder)
            self.in_file = os.path.join(ori_files_dir, ".in_file")
            os.symlink(os.path.join(ori_files_dir, ".file1"), self.in_file)

        output = TestBufferConanOutput()
        with environment_append({"CONAN_SKIP_BROKEN_SYMLINKS_CHECK": "True"}):
            self.gathered_files = gather_files(os.path.join(self.tmp_folder, "ori"), output=output)

    def test_warn_outside(self):
        output = TestBufferConanOutput()
        _compress_files(self.gathered_files, "compress.tar.gz", self.tmp_folder, output=output)
        self.assertEqual(str(output).count("WARN: Symbolic link"), 2)
        # Warn about the folder
        self.assertIn("WARN: Symbolic link '{}' points to".format(self.out_folder), output)
        # Want about the file
        self.assertIn("WARN: Symbolic link '{}' points to".format(self.out_file), output)

    def test_broken_file(self):
        os.unlink(os.path.join(self.tmp_folder, 'linked_file'))

        output = TestBufferConanOutput()
        with six.assertRaisesRegex(self, Exception, "No such file or directory:"
                                                    " '{}'".format(self.out_file)):
            _compress_files(self.gathered_files, "compress.tar.gz", self.tmp_folder, output=output)
        self.assertEqual(str(output).count("WARN: Symbolic link"), 1)

    def test_broken_directory(self):
        os.rmdir(os.path.join(self.tmp_folder, 'linked_folder'))

        output = TestBufferConanOutput()
        _compress_files(self.gathered_files, "compress.tar.gz", self.tmp_folder, output=output)
        self.assertEqual(str(output).count("WARN: Symbolic link"), 2)
        # TODO: Should raise exception?
