import unittest

from requests import Response

from conan.test.utils.tools import TestClient, TestServer, TestRequester

myconan1 = """
from conan import ConanFile
import platform

class HelloConan(ConanFile):
    name = "hello"
    version = "1.2.1"
"""


class DownloadTest(unittest.TestCase):

    def test_returns_on_failures(self):
        test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
        servers = {"default": test_server}

        class BuggyRequester(TestRequester):
            def get(self, *args, **kwargs):
                resp = Response()
                resp.status_code = 404
                resp._content = b''
                return resp

        client2 = TestClient(servers=servers, requester_class=BuggyRequester)
        client2.run("remote add remotename url")
        client2.run("install --requires=foo/bar@ -r remotename", assert_error=True)
        assert "Package 'foo/bar' not resolved: Unable to find 'foo/bar' in remotes" in client2.out

        class BuggyRequester2(BuggyRequester):
            def get(self, *args, **kwargs):
                resp = Response()
                resp.status_code = 500
                resp._content = b'This server is under maintenance'
                return resp

        client2 = TestClient(servers=servers, requester_class=BuggyRequester2)
        client2.run("remote add remotename url")
        client2.run("install --requires=foo/bar@ -r remotename", assert_error=True)
        assert "ERROR: Package 'foo/bar' not resolved" in client2.out
        assert "This server is under maintenance" in client2.out
        assert "not found" not in client2.out
