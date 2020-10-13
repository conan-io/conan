# coding=utf-8

import os
import unittest
from collections import namedtuple

import mock

from conans.client.conf.config_installer import _process_folder
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import save_files
from conans.test.utils.mocks import TestBufferConanOutput


class ProcessFolderTests(unittest.TestCase):
    def test_config_in_empty_folder(self):
        output = TestBufferConanOutput()
        cache_t = namedtuple("_", ["cache_folder", "remotes_path"])
        config_t = namedtuple("_", ["source_folder"])

        cache_folder = temp_folder()
        remotes_json = os.path.join(cache_folder, "registry.json")
        cache = cache_t(cache_folder=cache_folder, remotes_path=remotes_json)
        ori_folder = temp_folder()
        save_files(ori_folder, {'registry.json': 'whatever'})
        with mock.patch("conans.client.conf.config_installer.migrate_registry_file",
                        return_value=None):
            self.assertFalse(os.path.exists(remotes_json))
            _process_folder(config_t(None), ori_folder, cache, output)
        self.assertTrue(os.path.exists(remotes_json))
