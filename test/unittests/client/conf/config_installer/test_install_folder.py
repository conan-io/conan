import unittest
import os

from conans.client.conf.config_installer import tmp_config_install_folder
from conan.test.utils.test_files import temp_folder


class InstallFolderTests(unittest.TestCase):

    def test_unique_install_folder(self):
        """ Validate if tmp_config_install_folder is removing old folder before creating a new one

        tmp_config_install_folder must create the same folder, but all items must be exclude when a
        new folder is created.
        """
        cache_folder = temp_folder()

        with tmp_config_install_folder(cache_folder) as tmp_folder_first:
            temp_file = os.path.join(tmp_folder_first, "foobar.txt")
            open(temp_file, "w+")
            with tmp_config_install_folder(cache_folder) as tmp_folder_second:
                self.assertEqual(tmp_folder_first, tmp_folder_second)
                self.assertFalse(os.path.exists(temp_file))
