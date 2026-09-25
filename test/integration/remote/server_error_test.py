from requests import Response

from conan.internal import REVISIONS
from conan.test.utils.tools import TestClient, TestServer, TestRequester
from collections import namedtuple


class TestError200NoJson:

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
        assert "Response from remote is not json, but 'None'" in client.out

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
        assert "Remote responded with broken json: <>" in client.out

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
        assert "Unexpected server response [1, 2, 3]" in client.out


def test_unrecongized_exception():
    class BuggyRequester(TestRequester):
        def get(self, *args, **kwargs):
            resp = Response()
            resp.status_code = 444
            resp._content = 'some 444 error message'
            return resp

    c = TestClient(default_server_user=True, requester_class=BuggyRequester)
    c.run("install --requires=zlib/1.2 -r=default", assert_error=True)
    assert ("ERROR: Package 'zlib/1.2' not resolved: Server exception 444:"
            " some 444 error message") in c.out
