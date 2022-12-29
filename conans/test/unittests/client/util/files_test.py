import os
import sys
import time
import unittest

from conans.client.cmd.uploader import compress_files
from conans.paths import PACKAGE_TGZ_NAME
from conans.test.utils.test_files import temp_folder
from conans.util.files import md5sum, mkdir, path_exists, save


class FilesTest(unittest.TestCase):

    def test_md5_compress(self):
        """
        The md5 of a tgz should be the same if the files inside are the same
        """
        folder = temp_folder()
        save(os.path.join(folder, "one_file.txt"), b"The contents")
        save(os.path.join(folder, "Two_file.txt"), b"Two contents")

        files = {
            "one_file.txt": os.path.join(folder, "one_file.txt"),
            "Two_file.txt": os.path.join(folder, "Two_file.txt"),
        }

        compress_files(files, {}, PACKAGE_TGZ_NAME, dest_dir=folder)
        file_path = os.path.join(folder, PACKAGE_TGZ_NAME)

        md5_a = md5sum(file_path)
        if sys.version_info.major == 3 and sys.version_info.minor >= 9:
            # Python 3.9 changed the tar algorithm. Conan tgz will have different checksums
            # https://github.com/conan-io/conan/issues/8020
            self.assertEqual(md5_a, "79255eaf79cbb743da7cdb8786f4730a")
        else:
            self.assertEqual(md5_a, "df220cfbc0652e8992a89a77666c03b5")

        time.sleep(1)  # Timestamps change

        folder = temp_folder()
        compress_files(files, {}, PACKAGE_TGZ_NAME, dest_dir=folder)
        file_path = os.path.join(folder, PACKAGE_TGZ_NAME)

        md5_b = md5sum(file_path)

        self.assertEqual(md5_a, md5_b)

    def test_path_exists(self):
        """
        Unit test of path_exists
        """
        tmp_dir = temp_folder()
        tmp_dir = os.path.join(tmp_dir, "WhatEver")
        new_path = os.path.join(tmp_dir, "CapsDir")
        mkdir(new_path)
        self.assertTrue(path_exists(new_path, tmp_dir))
        self.assertFalse(path_exists(os.path.join(tmp_dir, "capsdir"), tmp_dir))
