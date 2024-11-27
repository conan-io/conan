import unittest

from requests.models import Response

from conan.test.utils.tools import TestClient

resp = Response()
resp._content = b'{"results": []}'
resp.status_code = 200
resp.headers = {"Content-Type": "application/json", "X-Conan-Server-Capabilities": "revisions"}


class RequesterMockTrue(object):

    def __init__(self, *args, **kwargs):
        pass

    def get(self, url, *args, **kwargs):
        assert "cacert.pem" in kwargs["verify"], "TEST FAILURE: cacert.pem not in verify kwarg"
        return resp


class RequesterMockFalse(object):

    def __init__(self, *args, **kwargs):
        pass

    def get(self, url, *args, **kwargs):
        assert kwargs["verify"] is False, "TEST FAILURE: verify arg is not False"
        return resp


class VerifySSLTest(unittest.TestCase):

    def test_verify_ssl(self):

        self.client = TestClient(requester_class=RequesterMockTrue)
        self.client.run("remote add myremote https://localhost --insecure")
        self.client.run("remote list")
        self.assertIn("Verify SSL: False", self.client.out)

        self.client.run("remote update myremote --url https://localhost --secure")
        self.client.run("remote list")
        self.assertIn("Verify SSL: True", self.client.out)

        self.client.run("remote remove myremote")
        self.client.run("remote add myremote https://localhost")
        self.client.run("remote list")
        self.assertIn("Verify SSL: True", self.client.out)

        # Verify that SSL is checked in requests
        self.client.run("search op* -r myremote")

        # Verify that SSL is not checked in requests
        self.client = TestClient(requester_class=RequesterMockFalse)
        self.client.run("remote add myremote https://localhost --insecure")
        self.client.run("search op* -r myremote")
