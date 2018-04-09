from conans.client import conan_api
import unittest


class ConfigTest(unittest.TestCase):

    def config_rm_test(self):
        conan, _, _ = conan_api.ConanAPIV1.factory()
        conan.config_set("proxies.https", "http://10.10.1.10:1080")
        self.assertIn("proxies", conan._client_cache.conan_config.sections())
        conan.config_rm('proxies')
        self.assertNotIn("proxies", conan._client_cache.conan_config.sections())
