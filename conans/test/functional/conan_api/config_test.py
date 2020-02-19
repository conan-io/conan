import unittest

from conans.client import conan_api


class ConfigTest(unittest.TestCase):

    def setUp(self):
        self.api, _, _ = conan_api.ConanAPIV1.factory()

    def config_rm_test(self):
        self.api.config_set("proxies.https", "http://10.10.1.10:1080")
        self.assertIn("proxies", self.api.app.config.sections())
        self.api.config_rm('proxies')
        self.assertNotIn("proxies", self.api.app.config.sections())

    def test_config_home(self):
        conan_home = self.api.config_home()
        self.assertEqual(self.api.cache_folder, conan_home)
