import unittest
from conans.test.utils.tools import TestClient
from requests.models import Response


resp = Response()
resp._content = b'{"results": []}'
resp.status_code = 200


class RequesterMockTrue(object):

    def __init__(self, *args, **kwargs):
        pass

    def get(self, url, *args, **kwargs):
        assert("cacert.pem" in kwargs["verify"])
        return resp


class RequesterMockFalse(object):

    def __init__(self, *args, **kwargs):
        pass

    def get(self, url, *args, **kwargs):
        assert(kwargs["verify"] is False)
        return resp


class VerifySSLTest(unittest.TestCase):

    def verify_ssl_test(self):

        self.client = TestClient(requester_class=RequesterMockTrue)
        self.client.run("remote add myremote https://localhost False")
        self.client.run("remote list")
        self.assertIn("Verify SSL: False", self.client.user_io.out)

        self.client.run("remote update myremote https://localhost True")
        self.client.run("remote list")
        self.assertIn("Verify SSL: True", self.client.user_io.out)

        self.client.run("remote remove myremote")
        self.client.run("remote add myremote https://localhost")
        self.client.run("remote list")
        self.assertIn("Verify SSL: True", self.client.user_io.out)

        # Verify that SSL is checked in requrests
        self.client.run("search op* -r myremote")

        # Verify that SSL is not checked in requests
        self.client = TestClient(requester_class=RequesterMockFalse)
        self.client.run("remote add myremote https://localhost False")
        self.client.run("search op* -r myremote")

