import os
import unittest

from conans.client.cmd.uploader import compress_files
from conan.internal.paths import PACKAGE_TGZ_NAME
from conan.test.utils.test_files import temp_folder
from conans.util.files import save


class RemoteManagerTest(unittest.TestCase):

    def test_compress_files(self):
        folder = temp_folder()
        save(os.path.join(folder, "one_file.txt"), "The contents")
        save(os.path.join(folder, "Two_file.txt"), "Two contents")

        files = {
            "one_file.txt": os.path.join(folder, "one_file.txt"),
            "Two_file.txt": os.path.join(folder, "Two_file.txt"),
        }

        path = compress_files(files, PACKAGE_TGZ_NAME, dest_dir=folder)
        self.assertTrue(os.path.exists(path))
        expected_path = os.path.join(folder, PACKAGE_TGZ_NAME)
        self.assertEqual(path, expected_path)
