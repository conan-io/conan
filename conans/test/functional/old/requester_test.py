import unittest
import textwrap

import six

from conans.client import tools
from conans.client.cache.cache import ClientCache
from conans.client.rest.conan_requester import ConanRequester
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestBufferConanOutput,\
    TestRequester, TestServer
from conans.util.files import save
import mock
from mock import Mock


class MyRequester(object):
    def __init__(self, *args, **kwargs):
        pass

    def get(self, _, **kwargs):
        return kwargs.get("timeout", "NOT SPECIFIED")


class RequesterTest(unittest.TestCase):

    def requester_timeout_test(self):
        cache = ClientCache(temp_folder(), TestBufferConanOutput())
        conf = """
[general]
request_timeout=2
"""
        save(cache.conan_conf_path, conf)
        cache.invalidate()
        requester = ConanRequester(cache, requester=MyRequester())
        self.assertEqual(requester.get("MyUrl"), 2.0)

        with tools.environment_append({"CONAN_REQUEST_TIMEOUT": "4.3"}):
            ConanRequester(cache, requester=MyRequester())
            self.assertEqual(requester.get("MyUrl"), 4.3)

    @mock.patch("conans.client.rest.conan_requester.ConanRequester")
    def requester_timeout_test_mock(self, requester):
        requester.get = Mock(return_value=404)
        client = TestClient(servers={"default": TestServer()})
        conf = textwrap.dedent("""
            [general]
            request_timeout=2
            """)
        save(client.cache.conan_conf_path, conf)
        client.run("search * -r=default")
        print client.out
        
        with tools.environment_append({"CONAN_REQUEST_TIMEOUT": "4.3"}):
            self.assertEqual(requester.get("MyUrl"), 4.3)

    def requester_timeout_errors_test(self):
        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
request_timeout=any_string
"""
        save(client.cache.conan_conf_path, conf)
        with six.assertRaisesRegex(self, Exception,
                                   "Specify a numeric parameter for 'request_timeout'"):
            client.run("install Lib/1.0@conan/stable")

    def no_request_timeout_test(self):
        # Test that not having timeout works
        cache = ClientCache(temp_folder(), TestBufferConanOutput())
        conf = textwrap.dedent("""
            [general]
            """)
        save(cache.conan_conf_path, conf)
        cache.invalidate()
        requester = ConanRequester(cache, requester=MyRequester())
        self.assertEqual(requester.get("MyUrl"), "NOT SPECIFIED")
