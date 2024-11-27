from requests import Response

from conan.test.utils.tools import TestClient, TestRequester


conanfile = """
from conan import ConanFile
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


class TestRequester:

    def test_requester_timeout(self):
        client = TestClient(requester_class=MyRequester)
        client.save_home({"global.conf": "core.net.http:timeout=4.3"})
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=foo --version=1.0")
        assert "TIMEOUT: 4.3" in client.out

    def test_requester_timeout_tuple(self):
        client = TestClient(requester_class=MyRequester)
        client.save_home({"global.conf": "core.net.http:timeout=(2, 3.4)"})
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=foo --version=1.0")
        assert "TIMEOUT: (2, 3.4)" in client.out

    def test_request_infinite_timeout(self):
        # Test that not having timeout works
        client = TestClient(requester_class=MyRequester)
        client.save_home({"global.conf": "core.net.http:timeout=-1"})
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=foo --version=1.0")
        assert "TIMEOUT: NOT SPECIFIED" in client.out

    def test_unset_request_timeout_use_default_one(self):
        client = TestClient(requester_class=MyRequester)
        client.save_home({"global.conf": "core.net.http:timeout=!"})
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=foo --version=1.0")
        assert "TIMEOUT: (30, 60)" in client.out
