import unittest
import os

from conans.test.utils.tools import TestClient
from conans.util.files import save
from conans.client.conan_api import get_basic_requester


class ProxiesConfTest(unittest.TestCase):
    def setUp(self):
        self.old_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)

    def test_requester(self):
        client = TestClient()
        conf = """
[proxies]
https=None
no_proxy=http://someurl,http://otherurl.com
http=http:/conan.url
        """
        save(client.client_cache.conan_conf_path, conf)
        requester = get_basic_requester(client.client_cache)
        self.assertEqual(requester.proxies, {"https": None,
                                             "http": "http:/conan.url"})
        self.assertEqual(os.environ["NO_PROXY"], "http://someurl,http://otherurl.com")
