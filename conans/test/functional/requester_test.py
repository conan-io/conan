import unittest

from conans import tools
from conans.test.utils.tools import TestClient
from conans.util.files import save


class MyRequester(object):

    def __init__(*args, **kwargs):
        pass

    def get(self, _, **kwargs):
        return kwargs.get("timeout", "NOT SPECIFIED")


class RequesterTest(unittest.TestCase):

    def requester_timeout_test(self):

        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
request_timeout=2
"""
        save(client.client_cache.conan_conf_path, conf)
        client.init_dynamic_vars()

        self.assertEquals(client.requester.get("MyUrl"), 2.0)

        with tools.environment_append({"CONAN_REQUEST_TIMEOUT": "4.3"}):
            client = TestClient(requester_class=MyRequester)
            client.init_dynamic_vars()
            self.assertEquals(client.requester.get("MyUrl"), 4.3)

    def requester_timeout_errors_test(self):
        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
request_timeout=any_string
"""
        save(client.client_cache.conan_conf_path, conf)
        with self.assertRaisesRegexp(Exception, "Specify a numeric parameter for 'request_timeout'"):
            client.run("install Lib/1.0@conan/stable")

    def no_request_timeout_test(self):
        # Test that not having timeout works
        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
"""
        save(client.client_cache.conan_conf_path, conf)
        client.init_dynamic_vars()
        self.assertEquals(client.requester.get("MyUrl"), "NOT SPECIFIED")



