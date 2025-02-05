import requests
from requests.models import Response

from conan.test.utils.tools import TestClient

resp = Response()
resp._content = b'{"results": []}'
resp.status_code = 200
resp.headers = {"Content-Type": "application/json", "X-Conan-Server-Capabilities": "revisions"}


class RequesterMockFalse:
    expected = False

    def __init__(self, *args, **kwargs):
        pass

    def get(self, url, *args, **kwargs):  # noqa
        assert kwargs["verify"] is self.expected
        return resp

    def Session(self):  # noqa
        return self

    @property
    def codes(self):
        return requests.codes

    def mount(self, *args, **kwargs):
        pass


class RequesterMockTrue(RequesterMockFalse):
    expected = True


class TestVerifySSL:

    def test_verify_ssl(self):
        c = TestClient(requester_class=RequesterMockTrue)
        c.run("remote add myremote https://localhost --insecure")
        c.run("remote list")
        assert "Verify SSL: False" in c.out

        c.run("remote update myremote --url https://localhost --secure")
        c.run("remote list")
        assert "Verify SSL: True" in c.out

        c.run("remote remove myremote")
        c.run("remote add myremote https://localhost")
        c.run("remote list")
        assert "Verify SSL: True" in c.out

        # Verify that SSL is checked in requests
        c.run("search op* -r myremote")
        assert "WARN: There are no matching recipe references" in c.out

        # Verify that SSL is not checked in requests
        c = TestClient(requester_class=RequesterMockFalse)
        c.run("remote add myremote https://localhost --insecure")
        c.run("search op* -r myremote")
        assert "WARN: There are no matching recipe references" in c.out
