import unittest

from conans.client import conan_api


class ConfigTest(unittest.TestCase):

    def setUp(self):
        self.conan, _, _ = conan_api.ConanAPIV1.factory()

    def config_rm_test(self):
        self.conan.config_set("proxies.https", "http://10.10.1.10:1080")
        self.assertIn("proxies", self.conan._cache.config.sections())
        self.conan.config_rm('proxies')
        self.assertNotIn("proxies", self.conan._cache.config.sections())

    def test_config_home(self):
        conan_home = self.conan.config_home()
        self.assertEqual(self.conan.cache_folder, conan_home)
