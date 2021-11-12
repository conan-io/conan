import unittest

from requests import Response

from conans.client import tools
from conans.test.utils.tools import TestClient, TestRequester
from conans.util.files import save


conanfile = """
from conans import ConanFile
from conan.tools.files import download

class HelloConan(ConanFile):
    def source(self):
        download(self, "http://foo", "bar.txt")
"""


class MyRequester(TestRequester):

    def get(self, _, **kwargs):
        print("TIMEOUT: {}".format(kwargs.get("timeout", "NOT SPECIFIED")))
        resp = Response()
        resp.status_code = 200
        resp._content = b''
        return resp


class RequesterTest(unittest.TestCase):

    def test_requester_timeout(self):

        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
request_timeout=2
"""
        save(client.cache.conan_conf_path, conf)

        with tools.environment_set({"CONAN_REQUEST_TIMEOUT": "4.3"}):
            client = TestClient(requester_class=MyRequester)
            client.save({"conanfile.py": conanfile})
            client.run("create . foo/1.0@")
            assert "TIMEOUT: 4.3" in client.out

    def test_requester_timeout_errors(self):
        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
request_timeout=any_string
"""
        save(client.cache.conan_conf_path, conf)
        with self.assertRaisesRegex(Exception,
                                   "Specify a numeric parameter for 'request_timeout'"):
            client.run("install Lib/1.0@conan/stable")

    def test_no_request_timeout(self):
        # Test that not having timeout works
        client = TestClient(requester_class=MyRequester)
        conf = """
[general]
"""
        save(client.cache.conan_conf_path, conf)
        client.save({"conanfile.py": conanfile})
        client.run("create . foo/1.0@")
        assert "TIMEOUT: NOT SPECIFIED" in client.out
