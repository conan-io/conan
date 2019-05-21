import os
import unittest

from conans.client import tools
from conans.client.rest.conan_requester import ConanRequester
from conans.test.utils.tools import TestClient, TestBufferConanOutput
from conans.util.files import save
from conans.test.utils.test_files import temp_folder
from conans.client.cache.cache import ClientCache
import textwrap


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
        save(client.cache.conan_conf_path, conf)

        cache = ClientCache(client.base_folder, TestBufferConanOutput())
        requester = ConanRequester(cache)

        def verify_proxies(url, **kwargs):
            self.assertEqual(kwargs["proxies"], {"https": None, "http": "http:/conan.url"})
            return "mocked ok!"

        requester._http_requester.get = verify_proxies
        self.assertEqual(os.environ["NO_PROXY"], "http://someurl,http://otherurl.com")
        self.assertEqual(requester.get("MyUrl"), "mocked ok!")

    def new_proxy_exclude_test(self):
        class MyRequester(object):
            def get(self, _, **kwargs):
                return "excluded!" if "proxies" not in kwargs else "not excluded!"

        cache = ClientCache(temp_folder(), TestBufferConanOutput())
        conf = textwrap.dedent("""
            [proxies]
            https=None
            no_proxy_match=MyExcludedUrl*, *otherexcluded_one*
            http=http://conan.url
            """)
        save(cache.conan_conf_path, conf)
        cache = ClientCache(cache.cache_folder, TestBufferConanOutput())
        requester = ConanRequester(cache, requester=MyRequester())
        self.assertEqual(requester.get("MyUrl"), "not excluded!")
        self.assertEqual(requester.get("**otherexcluded_one***"), "excluded!")
        self.assertEqual(requester.get("MyExcludedUrl***"), "excluded!")
        self.assertEqual(requester.get("**MyExcludedUrl***"), "not excluded!")

    def test_environ_kept(self):
        client = TestClient()
        conf = """
[proxies]
        """
        save(client.cache.conan_conf_path, conf)
        requester = ConanRequester(client.cache)

        def verify_env(url, **kwargs):
            self.assertTrue("HTTP_PROXY" in os.environ)

        with tools.environment_append({"HTTP_PROXY": "my_system_proxy"}):
            requester._http_requester.get = verify_env
            requester.get("MyUrl")

    def test_environ_removed(self):
        client = TestClient()
        conf = """
[proxies]
no_proxy_match=MyExcludedUrl*
"""
        save(client.cache.conan_conf_path, conf)
        cache = ClientCache(client.base_folder, TestBufferConanOutput())
        requester = ConanRequester(cache)

        def verify_env(url, **kwargs):
            self.assertFalse("HTTP_PROXY" in os.environ)
            self.assertFalse("http_proxy" in os.environ)

        with tools.environment_append({"http_proxy": "my_system_proxy"}):
            requester._http_requester.get = verify_env
            requester.get("MyUrl")
            self.assertEqual(os.environ["http_proxy"], "my_system_proxy")

        with tools.environment_append({"HTTP_PROXY": "my_system_proxy"}):
            requester._http_requester.get = verify_env
            requester.get("MyUrl")
            self.assertEqual(os.environ["HTTP_PROXY"], "my_system_proxy")
