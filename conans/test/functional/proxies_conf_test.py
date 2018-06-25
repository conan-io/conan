import unittest
import os

from conans import tools
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
        client.client_cache.invalidate()
        requester = get_basic_requester(client.client_cache)

        def verify_proxies(url, **kwargs):
            self.assertEquals(kwargs["proxies"], {"https": None, "http": "http:/conan.url"})
            return "mocked ok!"

        requester._requester.get = verify_proxies
        self.assertEqual(os.environ["NO_PROXY"], "http://someurl,http://otherurl.com")

        self.assertEquals(requester.get("MyUrl"), "mocked ok!")

    def new_proxy_exclude_test(self):

        class MyRequester(object):

            def __init__(*args, **kwargs):
                pass

            def get(self, _, **kwargs):
                return "excluded!" if "proxies" not in kwargs else "not excluded!"

        client = TestClient(requester_class=MyRequester)
        conf = """
[proxies]
https=None
no_proxy_match=MyExcludedUrl*, *otherexcluded_one*
http=http://conan.url
        """
        save(client.client_cache.conan_conf_path, conf)
        client.init_dynamic_vars()

        self.assertEquals(client.requester.get("MyUrl"), "not excluded!")
        self.assertEquals(client.requester.get("**otherexcluded_one***"), "excluded!")
        self.assertEquals(client.requester.get("MyExcludedUrl***"), "excluded!")
        self.assertEquals(client.requester.get("**MyExcludedUrl***"), "not excluded!")

    def test_environ_kept(self):
        client = TestClient()
        conf = """
[proxies]
        """
        save(client.client_cache.conan_conf_path, conf)
        client.client_cache.invalidate()
        requester = get_basic_requester(client.client_cache)

        def verify_env(url, **kwargs):
            self.assertTrue("HTTP_PROXY" in os.environ)

        with tools.environment_append({"HTTP_PROXY": "my_system_proxy"}):
            requester._requester.get = verify_env
            requester.get("MyUrl")

    def test_environ_removed(self):

        client = TestClient()
        conf = """
[proxies]
no_proxy_match=MyExcludedUrl*
"""
        save(client.client_cache.conan_conf_path, conf)
        client.client_cache.invalidate()
        requester = get_basic_requester(client.client_cache)

        def verify_env(url, **kwargs):
            self.assertFalse("HTTP_PROXY" in os.environ)
            self.assertFalse("http_proxy" in os.environ)

        with tools.environment_append({"http_proxy": "my_system_proxy"}):
            requester._requester.get = verify_env
            requester.get("MyUrl")
            self.assertEqual(os.environ["http_proxy"], "my_system_proxy")

        with tools.environment_append({"HTTP_PROXY": "my_system_proxy"}):
            requester._requester.get = verify_env
            requester.get("MyUrl")
            self.assertEqual(os.environ["HTTP_PROXY"], "my_system_proxy")
