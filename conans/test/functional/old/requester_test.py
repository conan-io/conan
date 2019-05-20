import unittest
import textwrap

import six

from conans.client import tools
from conans.test.utils.tools import TestClient, TestServer, TestRequester
from conans.util.files import save


class RequesterTest(unittest.TestCase):

    def requester_timeout_test(self):
        calls = []

        class MyTestRequester(TestRequester):
            def get(self, url, **kwargs):
                calls.append(kwargs)
                return super(MyTestRequester, self).get(url, **kwargs)

        client = TestClient(servers={"default": TestServer()}, requester_class=MyTestRequester)
        conf = textwrap.dedent("""
            [general]
            request_timeout=2
            """)
        save(client.cache.conan_conf_path, conf)
        client.run("search * -r=default")
        self.assertEqual(2, len(calls))
        self.assertEqual(2.0, calls[0]["timeout"])
        self.assertEqual(2.0, calls[1]["timeout"])

        conf = textwrap.dedent("""
            [general]
            """)
        save(client.cache.conan_conf_path, conf)
        client.run("search * -r=default")
        self.assertEqual(4, len(calls))
        self.assertIsNone(calls[2].get("timeout"))
        self.assertIsNone(calls[3].get("timeout"))

        with tools.environment_append({"CONAN_REQUEST_TIMEOUT": "4.3"}):
            client.run("search * -r=default")
            self.assertEqual(6, len(calls))
            self.assertEqual(4.3, calls[4]["timeout"])
            self.assertEqual(4.3, calls[5]["timeout"])

    def requester_timeout_errors_test(self):
        client = TestClient()
        conf = """
[general]
request_timeout=any_string
"""
        save(client.cache.conan_conf_path, conf)
        with six.assertRaisesRegex(self, Exception,
                                   "Specify a numeric parameter for 'request_timeout'"):
            client.run("install Lib/1.0@conan/stable")
