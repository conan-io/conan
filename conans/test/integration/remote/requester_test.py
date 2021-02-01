import unittest

import six

from conans.client import tools
from conans.test.utils.tools import TestClient
from conans.util.files import save


class MyRequester(object):

    def __init__(*args, **kwargs):
        pass

    def get(self, _, **kwargs):
        return kwargs.get("timeout", "NOT SPECIFIED")


class RequesterTest(unittest.TestCase):

    def test_requester_timeout(self):

        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
request_timeout=2
"""
        save(client.cache.conan_conf_path, conf)

        self.assertEqual(client.requester.get("MyUrl"), 2.0)

        with tools.environment_append({"CONAN_REQUEST_TIMEOUT": "4.3"}):
            client = TestClient(requester_class=MyRequester)
            self.assertEqual(client.requester.get("MyUrl"), 4.3)

    def test_requester_timeout_errors(self):
        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
request_timeout=any_string
"""
        save(client.cache.conan_conf_path, conf)
        with six.assertRaisesRegex(self, Exception,
                                   "Specify a numeric parameter for 'request_timeout'"):
            client.run("install Lib/1.0@conan/stable")

    def test_no_request_timeout(self):
        # Test that not having timeout works
        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
"""
        save(client.cache.conan_conf_path, conf)
        self.assertEqual(client.requester.get("MyUrl"), "NOT SPECIFIED")
