import os
import unittest
from parameterized import parameterized

from conans.client.conf.config_installer import _process_config_install_item
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ConfigInstallerTests(unittest.TestCase):

    def process_config_install_item_test(self):
        config_type, url_or_path, args = _process_config_install_item(
                "git:[whaterver.url.com/repo.git, --recusrive --other -b 0.3.4]")
        self.assertEqual("git", config_type)
        self.assertEqual("whaterver.url.com/repo.git", url_or_path)
        self.assertEqual("--recusrive --other -b 0.3.4", args)

        config_type, url_or_path, args = _process_config_install_item("whaterver.url.com/repo.git")
        self.assertEqual("git", config_type)
        self.assertEqual("whaterver.url.com/repo.git", url_or_path)
        self.assertIsNone(args)

        dir_path = temp_folder()
        for dir_item in ["dir:[%s, None]" % dir_path, dir_path]:
            config_type, url_or_path, args = _process_config_install_item(dir_item)
            self.assertEqual("dir", config_type)
            self.assertEqual(dir_path, url_or_path)
            self.assertIsNone(args)

        file_path = os.path.join(dir_path, "file.zip")
        save(file_path, "")
        for file_item in ["file:[%s, None]" % file_path, file_path]:
            config_type, url_or_path, args = _process_config_install_item(file_item)
            self.assertEqual("file", config_type)
            self.assertEqual(file_path, url_or_path)
            self.assertIsNone(args)

        for url_item in ["url:[http://is/an/absloute/path with spaces/here/file.zip, None]",
                         "http://is/an/absloute/path with spaces/here/file.zip"]:
            config_type, url_or_path, args = _process_config_install_item(url_item)
            self.assertEqual("url", config_type)
            self.assertEqual("http://is/an/absloute/path with spaces/here/file.zip", url_or_path)
            self.assertIsNone(args)

        config_type, url, args = _process_config_install_item(
                "url:[http://is/an/absloute/path with spaces/here/file.zip, --option]")
        self.assertEqual("url", config_type)
        self.assertEqual("http://is/an/absloute/path with spaces/here/file.zip", url)
        self.assertEqual("--option", args)

        # Test wrong input
        for item in ["git@github.com:conan-io/conan.git, None"
                     "file/not/exists.zip"]:
            with self.assertRaisesRegex(ConanException, "Unable to process config install"):
                _, _, _ = _process_config_install_item(item)
