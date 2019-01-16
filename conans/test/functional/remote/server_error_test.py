import unittest


from conans.test.utils.tools import TestClient, TestServer
from collections import namedtuple


class Error200NoJson(unittest.TestCase):

    def test_error_json(self):
        class RequesterMock(object):
            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                # Response must be binary, it is decoded in RestClientCommon
                return namedtuple("Response", "status_code headers content")(200, {}, b'<>')

        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": TestServer()},
                            requester_class=RequesterMock,
                            users={"default": [("lasote", "mypass")]})

        client.run("install pkg/ref@user/testing", assert_error=True)
        self.assertIn("ERROR: Remote responded with unexpected message: <>", client.out)
