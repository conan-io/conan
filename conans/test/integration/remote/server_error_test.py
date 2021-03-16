import unittest


from conans.test.utils.tools import TestClient, TestServer
from collections import namedtuple


class Error200NoJson(unittest.TestCase):

    def test_error_no_json(self):
        class RequesterMock(object):
            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):  # @UnusedVariable
                # Response must be binary, it is decoded in RestClientCommon
                return namedtuple("Response", "status_code headers content ok")(200, {}, b'<>',
                                                                                True)

        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": TestServer()},
                            requester_class=RequesterMock,
                            users={"default": [("lasote", "mypass")]})

        client.run("install pkg/ref@user/testing", assert_error=True)
        self.assertIn("ERROR: <>", client.out)
        self.assertIn("Response from remote is not json, but 'None'", client.out)

    def test_error_broken_json(self):
        class RequesterMock(object):
            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):  # @UnusedVariable
                # Response must be binary, it is decoded in RestClientCommon
                headers = {"Content-Type": "application/json"}
                return namedtuple("Response", "status_code headers content ok")(200, headers,
                                                                                b'<>', True)

        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": TestServer()},
                            requester_class=RequesterMock,
                            users={"default": [("lasote", "mypass")]})

        client.run("install pkg/ref@user/testing", assert_error=True)
        self.assertIn("Remote responded with broken json: <>", client.out)

    def test_error_json(self):
        class RequesterMock(object):
            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):  # @UnusedVariable
                # Response must be binary, it is decoded in RestClientCommon
                headers = {"Content-Type": "application/json"}
                return namedtuple("Response", "status_code headers content ok")(200, headers,
                                                                                b'[1, 2, 3]', True)

        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": TestServer()},
                            requester_class=RequesterMock,
                            users={"default": [("lasote", "mypass")]})

        client.run("install pkg/ref@user/testing", assert_error=True)
        self.assertIn("ERROR: Unexpected server response [1, 2, 3]", client.out)
