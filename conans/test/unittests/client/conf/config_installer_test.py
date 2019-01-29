import os
import unittest
import tempfile

from conans.client.conf.config_installer import _process_config_install_item, _handle_config_files
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class ConfigInstallerTests(unittest.TestCase):

    def process_config_install_item_test(self):
        config_type, url_or_path, verify_ssl, args = _process_config_install_item(
                "git, whaterver.url.com/repo.git, False, --recusrive --other -b 0.3.4")
        self.assertEqual("git", config_type)
        self.assertEqual("whaterver.url.com/repo.git", url_or_path)
        self.assertFalse(verify_ssl)
        self.assertEqual("--recusrive --other -b 0.3.4", args)

        config_type, url_or_path, verify_ssl, args = _process_config_install_item("whaterver.url.com/repo.git")
        self.assertEqual("git", config_type)
        self.assertEqual("whaterver.url.com/repo.git", url_or_path)
        self.assertIsNone(verify_ssl)
        self.assertIsNone(args)

        dir_path = temp_folder()
        for dir_item in ["dir, %s, True, None" % dir_path, dir_path]:
            config_type, url_or_path, verify_ssl, args = _process_config_install_item(dir_item)
            self.assertEqual("dir", config_type)
            self.assertEqual(dir_path, url_or_path)
            self.assertTrue(verify_ssl) if dir_item.startswith("dir,")\
                else self.assertIsNone(verify_ssl)
            self.assertIsNone(args)

        file_path = os.path.join(dir_path, "file.zip")
        save(file_path, "")
        for file_item in ["file, %s, True, None" % file_path, file_path]:
            config_type, url_or_path, verify_ssl, args = _process_config_install_item(file_item)
            self.assertEqual("file", config_type)
            self.assertEqual(file_path, url_or_path)
            self.assertTrue(verify_ssl) if file_item.startswith("file,") \
                else self.assertIsNone(verify_ssl)
            self.assertIsNone(args)

        for url_item in ["url, http://is/an/absloute/path with spaces/here/file.zip, True, None",
                         "http://is/an/absloute/path with spaces/here/file.zip"]:
            config_type, url_or_path, verify_ssl, args = _process_config_install_item(url_item)
            self.assertEqual("url", config_type)
            self.assertEqual("http://is/an/absloute/path with spaces/here/file.zip", url_or_path)
            self.assertTrue(verify_ssl) if url_item.startswith("url,") \
                else self.assertIsNone(verify_ssl)
            self.assertIsNone(args)

        config_type, url, verify_ssl, args = _process_config_install_item(
                "url,   http://is/an/absloute/path with spaces/here/file.zip,False, --option  ")
        self.assertEqual("url", config_type)
        self.assertEqual("http://is/an/absloute/path with spaces/here/file.zip", url)
        self.assertFalse(verify_ssl)
        self.assertEqual("--option", args)

        # Test wrong input
        for item in ["git@github.com:conan-io/conan.git, None"
                     "file/not/exists.zip"]:
            with self.assertRaisesRegexp(ConanException, "Unable to process config install"):
                _, _, _, _ = _process_config_install_item(item)

    def handle_config_files_test(self):
        src_dir = temp_folder()
        target_dir = temp_folder()
        temp_files = []
        output = TestBufferConanOutput()

        for _ in range(10):
            _, path = tempfile.mkstemp(dir=src_dir)
            temp_files.append(path)

        _handle_config_files(source_folder=src_dir, target_folder=target_dir, output=output)

        for file_name in temp_files:
            expected_path = os.path.join(target_dir, file_name)
            self.assertTrue(os.path.exists(expected_path))
            self.assertTrue(os.path.isfile(expected_path))
