import os
import unittest

from conans import tools
from conans.client import conan_api
from conans.client.cache.cache import CONAN_CONF
from conans.client.conf import get_default_client_conf
from conans.test.utils.test_files import temp_folder
from conans.tools import save


class ConfigTest(unittest.TestCase):

    def setUp(self):
        tmp = temp_folder()
        conf = get_default_client_conf()
        os.mkdir(os.path.join(tmp, ".conan"))
        save(os.path.join(tmp, ".conan", CONAN_CONF), conf)
        with tools.environment_append({"CONAN_USER_HOME": tmp}):
            self.api, _, _ = conan_api.ConanAPIV1.factory()

    def test_config_rm(self):
        self.api.config_set("proxies.https", "http://10.10.1.10:1080")
        self.assertIn("proxies", self.api.app.config.sections())
        self.api.config_rm('proxies')
        self.assertNotIn("proxies", self.api.app.config.sections())

    def test_config_home(self):
        conan_home = self.api.config_home()
        self.assertEqual(self.api.cache_folder, conan_home)
