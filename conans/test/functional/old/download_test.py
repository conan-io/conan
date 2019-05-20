import unittest

from conans.test.utils.tools import TestClient, TestServer


class DownloadTest(unittest.TestCase):

    def test_returns_on_failures(self):
        class Response(object):
            ok = None
            status_code = None
            charset = None
            text = ""
            headers = {}

            def __init__(self, ok, status_code, text):
                self.ok = ok
                self.status_code = status_code
                self.text = text

        class BuggyRequester(object):
            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                return Response(False, 500, "VERY BAD ERROR!")

        client = TestClient(servers={"default": TestServer()},
                            requester_class=BuggyRequester)
        client.run("install Hello/1.2.1@frodo/stable -r=default", assert_error=True)
        self.assertIn("ERROR: VERY BAD ERROR!. [Remote: default]", client.out)
