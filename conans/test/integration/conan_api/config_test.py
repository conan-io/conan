import os
import unittest

from conans.cli.api.conan_api import ConanAPIV2
from conans.client.cache.cache import CONAN_CONF
from conans.client.conf import get_default_client_conf
from conans.paths import DEFAULT_CONAN_HOME
from conans.test.utils.test_files import temp_folder
from conans.tools import save
from conans.util.env import environment_update


class ConfigTest(unittest.TestCase):

    def setUp(self):
        user_home = temp_folder()
        conf = get_default_client_conf()
        self._cache_folder = os.path.join(user_home, DEFAULT_CONAN_HOME)
        os.mkdir(self._cache_folder)
        save(os.path.join(self._cache_folder, CONAN_CONF), conf)
        with environment_update({"CONAN_HOME": user_home}):
            self.api = ConanAPIV2()

    def test_config_home(self):
        conan_home = self.api.config.home()
        self.assertEqual(self.api.cache_folder, conan_home)
