import os
import unittest
import textwrap
import warnings
from mock import patch


from conans.client import tools
from conans.client.rest.conan_requester import ConanRequester
from conans.test.utils.tools import TestClient
from conans.util.files import save


@patch.dict('os.environ', {})
class ProxiesConfTest(unittest.TestCase):

    def test_requester(self):
        client = TestClient()
        conf = """
[proxies]
https=None
no_proxy=http://someurl,http://otherurl.com
http=http://conan.url
        """
        save(client.cache.conan_conf_path, conf)
        with warnings.catch_warnings(record=True) as warn:
            warnings.simplefilter("always")
            requester = ConanRequester(client.cache.config)

            def verify_proxies(url, **kwargs):
                self.assertEqual(kwargs["proxies"], {"https": None, "http": "http://conan.url"})
                return "mocked ok!"

            requester._http_requester.get = verify_proxies
            self.assertEqual(os.environ["NO_PROXY"], "http://someurl,http://otherurl.com")

            self.assertEqual(requester.get("MyUrl"), "mocked ok!")

            self.assertEqual(1, len(warn))
            self.assertTrue(issubclass(warn[-1].category, UserWarning))
            self.assertIn("proxies.no_proxy has been deprecated. "
                          "Use proxies.no_proxy_match instead", str(warn[-1].message))

    def test_requester_with_host_specific_proxies(self):
        client = TestClient()
        conf = textwrap.dedent("""
            [proxies]
            https=http://conan.url
              only.for.this.conan.url = http://special.url
              only.for.that.conan.url = http://user:pass@extra.special.url
            http=
              only.for.the.other.conan.url = http://other.special.url
                    """)
        save(client.cache.conan_conf_path, conf)
        requester = ConanRequester(client.cache.config)

        def verify_proxies(url, **kwargs):
            self.assertEqual(kwargs["proxies"],
                             {"http://only.for.the.other.conan.url": "http://other.special.url",
                              "https": "http://conan.url",
                              "https://only.for.this.conan.url": "http://special.url",
                              "https://only.for.that.conan.url":
                              "http://user:pass@extra.special.url"})
            return "mocked ok!"

        requester._http_requester.get = verify_proxies
        self.assertFalse("NO_PROXY" in os.environ, "Error: NO_PROXY=%s" % os.getenv("NO_PROXY"))

        self.assertEqual(requester.get("MyUrl"), "mocked ok!")

    def test_new_proxy_exclude(self):

        class MyRequester(object):

            def __init__(self, *args, **kwargs):
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
        save(client.cache.conan_conf_path, conf)

        self.assertEqual(client.requester.get("MyUrl"), "not excluded!")
        self.assertEqual(client.requester.get("**otherexcluded_one***"), "excluded!")
        self.assertEqual(client.requester.get("MyExcludedUrl***"), "excluded!")
        self.assertEqual(client.requester.get("**MyExcludedUrl***"), "not excluded!")

    def test_environ_kept(self):
        client = TestClient()
        conf = """
[proxies]
        """
        save(client.cache.conan_conf_path, conf)
        requester = ConanRequester(client.cache.config)

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
        requester = ConanRequester(client.cache.config)

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
