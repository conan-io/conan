import os
import unittest

from conans.client.cmd.uploader import _compress_files, _GatheredFiles
from conans.paths import PACKAGE_TGZ_NAME
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class RemoteManagerTest(unittest.TestCase):

    def test_compress_files(self):
        folder = temp_folder()
        save(os.path.join(folder, "one_file.txt"), b"The contents")
        save(os.path.join(folder, "Two_file.txt"), b"Two contents")

        files = {
            "one_file.txt": os.path.join(folder, "one_file.txt"),
            "Two_file.txt": os.path.join(folder, "Two_file.txt"),
        }

        gathered_files = _GatheredFiles("", files, {})
        path = _compress_files(gathered_files, PACKAGE_TGZ_NAME, dest_dir=folder, output=None)
        self.assertTrue(os.path.exists(path))
        expected_path = os.path.join(folder, PACKAGE_TGZ_NAME)
        self.assertEqual(path, expected_path)
