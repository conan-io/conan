# coding=utf-8

import unittest

from conans.client.conf.config_installer import tmp_config_install_folder
from conans.test.utils.tools import TestClient


class InstallFolderTests(unittest.TestCase):

    def test_unique_install_folder(self):
        client = TestClient()

        with tmp_config_install_folder(client.cache) as tmp_folder_first:
            with tmp_config_install_folder(client.cache) as tmp_folder_second:
                self.assertNotEqual(tmp_folder_first, tmp_folder_second)
