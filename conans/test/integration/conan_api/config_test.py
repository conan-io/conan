import os
import unittest

from conans import tools
from conans.cli.conan_app import ConanApp
from conans.client import conan_api
from conans.client.cache.cache import CONAN_CONF
from conans.client.conf import get_default_client_conf
from conans.test.utils.test_files import temp_folder
from conans.tools import save


class ConfigTest(unittest.TestCase):

    def setUp(self):
        user_home = temp_folder()
        conf = get_default_client_conf()
        self._cache_folder = os.path.join(user_home, ".conan")
        os.mkdir(self._cache_folder)
        save(os.path.join(self._cache_folder, CONAN_CONF), conf)
        with tools.environment_append({"CONAN_USER_HOME": user_home}):
            self.api = conan_api.ConanAPIV1()

    def test_config_rm(self):
        self.api.config_set("proxies.https", "http://10.10.1.10:1080")

        app = ConanApp(self._cache_folder)
        self.assertIn("proxies", app.config.sections())
        self.api.config_rm('proxies')

        app = ConanApp(self._cache_folder)
        self.assertNotIn("proxies", app.config.sections())

    def test_config_home(self):
        conan_home = self.api.config_home()
        self.assertEqual(self.api.cache_folder, conan_home)
