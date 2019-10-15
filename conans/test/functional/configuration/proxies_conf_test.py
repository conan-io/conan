import os
import unittest
import textwrap
import warnings
import platform
from mock import patch


from conans.client import tools
from conans.client.rest.conan_requester import ConanRequester
from conans.test.utils.tools import TestClient
from conans.util.files import save

from requests.adapters import HTTPAdapter
from mock import mock


class ConanAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        super(ConanAdapter, self).__init__(*args, **kwargs)
        self._proxies = None

    def send(self, request, stream=False, timeout=None, verify=True,
             cert=None, proxies=None):
        self._proxies = proxies

        raise ValueError("invalid")

    @property
    def proxies(self):
        return dict(self._proxies)


@patch.dict('os.environ', {})
class ProxiesConfTest(unittest.TestCase):

    @property
    def names_of_platform_proxy_function(self):
        if platform.system() == "Darwin":
            try:
                from urllib.request import getproxies_macosx_sysconf  # pylint: disable=unused-import
                return "urllib.request.getproxies_macosx_sysconf"
            except ImportError:
                from urllib import getproxies_macosx_sysconf  # pylint: disable=unused-import
                return "urllib.getproxies_macosx_sysconf"
        elif platform.system() == "Windows":
            try:
                from urllib.request import getproxies_registry  # pylint: disable=unused-import
                return "urllib.request.getproxies_registry"
            except ImportError:
                from urllib import getproxies_registry  # pylint: disable=unused-import
                return "urllib.getproxies_registry"

    @unittest.skipUnless(platform.system() in ["Darwin", "Windows"], "Requires OSX or Windows")
    def test_no_proxies_section(self):
        client = TestClient()
        conf = """
"""
        save(client.cache.conan_conf_path, conf)

        requester = ConanRequester(client.cache.config)
        conan_adapter = ConanAdapter()
        requester._http_requester.mount("conan", conan_adapter)

        system_proxies = {
            "http": "example.com:80",
            "https": "example.com:443"
        }
        env_proxies_vars = {
            'HTTP_PROXY': "conan.io:80",
            "HTTPS_PROXY": "conan.io:443"
        }
        env_proxies = {
            'http': "conan.io:80",
            "https": "conan.io:443"
        }

        with mock.patch(self.names_of_platform_proxy_function,
                        mock.MagicMock(return_value=system_proxies)):
            with tools.environment_append(env_proxies_vars):
                with self.assertRaises(ValueError):
                    requester.get("conan://MyUrl")

        self.assertEqual(conan_adapter.proxies, env_proxies)

        with mock.patch(self.names_of_platform_proxy_function,
                        mock.MagicMock(return_value=system_proxies)):
            with self.assertRaises(ValueError):
                requester.get("conan://MyUrl")

        self.assertEqual(conan_adapter.proxies, system_proxies)

    @unittest.skipUnless(platform.system() in ["Darwin", "Windows"], "Requires OSX or Windows")
    def test_empty_proxies_section(self):
        client = TestClient()
        conf = """
[proxies]
"""
        save(client.cache.conan_conf_path, conf)

        requester = ConanRequester(client.cache.config)
        conan_adapter = ConanAdapter()
        requester._http_requester.mount("conan", conan_adapter)

        system_proxies = {
            "http": "example.com:80",
            "https": "example.com:443"
        }
        env_proxies_vars = {
            'HTTP_PROXY': "conan.io:80",
            "HTTPS_PROXY": "conan.io:443"
        }
        env_proxies = {
            'http': "conan.io:80",
            "https": "conan.io:443"
        }

        with mock.patch(self.names_of_platform_proxy_function,
                        mock.MagicMock(return_value=system_proxies)):
            with tools.environment_append(env_proxies_vars):
                with self.assertRaises(ValueError):
                    requester.get("conan://MyUrl")

        self.assertEqual(conan_adapter.proxies, env_proxies)

        with mock.patch(self.names_of_platform_proxy_function,
                        mock.MagicMock(return_value=system_proxies)):
            with self.assertRaises(ValueError):
                requester.get("conan://MyUrl")

        self.assertEqual(conan_adapter.proxies, system_proxies)

    @unittest.skipUnless(platform.system() in ["Darwin", "Windows"], "Requires OSX or Windows")
    def test_disable_system_proxy(self):
        client = TestClient()
        conf = """
[proxies]
use_system_proxy = False
"""
        save(client.cache.conan_conf_path, conf)

        requester = ConanRequester(client.cache.config)
        conan_adapter = ConanAdapter()
        requester._http_requester.mount("conan", conan_adapter)

        system_proxies = {
            "http": "example.com:80",
            "https": "example.com:443"
        }
        env_proxies_vars = {
            'HTTP_PROXY': "conan.io:80",
            "HTTPS_PROXY": "conan.io:443"
        }

        with mock.patch(self.names_of_platform_proxy_function,
                        mock.MagicMock(return_value=system_proxies)):
            with tools.environment_append(env_proxies_vars):
                with self.assertRaises(ValueError):
                    requester.get("conan://MyUrl")

        self.assertEqual(conan_adapter.proxies, {})

        with mock.patch(self.names_of_platform_proxy_function,
                        mock.MagicMock(return_value=system_proxies)):
            with self.assertRaises(ValueError):
                requester.get("conan://MyUrl")

        self.assertEqual(conan_adapter.proxies, {})

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

    def new_proxy_exclude_test(self):

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
