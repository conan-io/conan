import pytest
from requests import Response

from conans.test.utils.tools import TestClient, TestRequester


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


class TestRequester:

    def test_requester_timeout(self):
        client = TestClient(requester_class=MyRequester)
        client.save({"global.conf": "core.net.http:timeout=4.3"}, path=client.cache.cache_folder)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=foo --version=1.0")
        assert "TIMEOUT: 4.3" in client.out

    def test_requester_timeout_tuple(self):
        client = TestClient(requester_class=MyRequester)
        client.save({"global.conf": "core.net.http:timeout=(2, 3.4)"},
                    path=client.cache.cache_folder)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=foo --version=1.0")
        assert "TIMEOUT: (2, 3.4)" in client.out

    def test_requester_timeout_errors(self):
        client = TestClient(requester_class=MyRequester)
        client.save({"global.conf": "core.net.http:timeout=invalid"}, path=client.cache.cache_folder)
        with pytest.raises(Exception) as e:
            client.run("install --reference=Lib/1.0@conan/stable")
        assert "Conf 'core.net.http:timeout' value 'invalid' must be" in str(e.value)

    def test_no_request_timeout(self):
        # Test that not having timeout works
        client = TestClient(requester_class=MyRequester)
        client.save({"global.conf": "core.net.http:timeout=None"}, path=client.cache.cache_folder)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=foo --version=1.0")
        assert "TIMEOUT: NOT SPECIFIED" in client.out
