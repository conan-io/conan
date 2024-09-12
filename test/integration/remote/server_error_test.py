import unittest

from conans import REVISIONS
from conan.test.utils.tools import TestClient, TestServer, TestRequester
from collections import namedtuple


class Error200NoJson(unittest.TestCase):

    def test_error_no_json(self):
        class RequesterMock(TestRequester):
            def get(self, *args, **kwargs):  # @UnusedVariable
                # Response must be binary, it is decoded in RestClientCommon
                headers = {"X-Conan-Server-Capabilities": REVISIONS}
                return namedtuple("Response", "status_code headers content ok")(200, headers, b'<>',
                                                                                True)
        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": TestServer()},
                            requester_class=RequesterMock,
                            inputs=["admin", "password"])

        client.run("install --requires=pkg/ref@user/testing", assert_error=True)
        self.assertIn("Response from remote is not json, but 'None'", client.out)

    def test_error_broken_json(self):
        class RequesterMock(TestRequester):
            def get(self, *args, **kwargs):  # @UnusedVariable
                # Response must be binary, it is decoded in RestClientCommon
                headers = {"Content-Type": "application/json",
                           "X-Conan-Server-Capabilities": REVISIONS}
                return namedtuple("Response", "status_code headers content ok")(200, headers,
                                                                                b'<>', True)

        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": TestServer()},
                            requester_class=RequesterMock,
                            inputs=["admin", "password"])

        client.run("install --requires=pkg/ref@user/testing", assert_error=True)
        self.assertIn("Remote responded with broken json: <>", client.out)

    def test_error_json(self):
        class RequesterMock(TestRequester):

            def get(self, *args, **kwargs):  # @UnusedVariable
                # Response must be binary, it is decoded in RestClientCommon
                headers = {"Content-Type": "application/json",
                           "X-Conan-Server-Capabilities": REVISIONS}
                return namedtuple("Response", "status_code headers content ok")(200, headers,
                                                                                b'[1, 2, 3]', True)

        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": TestServer()},
                            requester_class=RequesterMock,
                            inputs=["admin", "password"])

        client.run("install --requires=pkg/ref@user/testing", assert_error=True)
        self.assertIn("Unexpected server response [1, 2, 3]", client.out)
