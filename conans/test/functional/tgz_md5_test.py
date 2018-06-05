import os
import time
import unittest

from conans.test.utils.test_files import temp_folder
from conans.util.files import save, md5sum
from conans.paths import PACKAGE_TGZ_NAME
from conans.client.remote_manager import compress_files


class TgzMd5Test(unittest.TestCase):
    """The md5 of a tgz should be the same if the files inside are the same"""

    def test_md5_compress(self):
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
        self.assertEqual(md5_a, "df220cfbc0652e8992a89a77666c03b5")

        time.sleep(1)  # Timestamps change

        folder = temp_folder()
        compress_files(files, {}, PACKAGE_TGZ_NAME, dest_dir=folder)
        file_path = os.path.join(folder, PACKAGE_TGZ_NAME)

        md5_b = md5sum(file_path)

        self.assertEquals(md5_a, md5_b)
