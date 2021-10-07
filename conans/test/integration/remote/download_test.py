import unittest

from conans.client.recorder.action_recorder import ActionRecorder
from conans.errors import ConanException, NotFoundException
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer
from conans.client.cache.remote_registry import Remotes

myconan1 = """
from conans import ConanFile
import platform

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
"""


class DownloadTest(unittest.TestCase):

    def test_returns_on_failures(self):
        test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
        servers = {"default": test_server}

        class Response(object):
            ok = None
            status_code = None
            charset = None
            text = ""
            headers = {}
            content = ""

            def __init__(self, ok, status_code):
                self.ok = ok
                self.status_code = status_code

        class BuggyRequester(object):

            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                return Response(False, 404)

        client2 = TestClient(servers=servers, requester_class=BuggyRequester)
        ref = ConanFileReference.loads("Hello/1.2.1@frodo/stable")
        proxy = client2.proxy

        remotes = Remotes()
        remotes.add("remotename", "url")
        with self.assertRaises(NotFoundException):
            proxy.get_recipe(ref, False, False, remotes, ActionRecorder())

        class BuggyRequester2(BuggyRequester):
            def get(self, *args, **kwargs):
                return Response(False, 500)

        client2 = TestClient(servers=servers, requester_class=BuggyRequester2)
        proxy = client2.proxy

        try:
            proxy.get_recipe(ref, False, False, remotes, ActionRecorder())
        except NotFoundException:
            self.assertFalse(True)  # Shouldn't capture here
        except ConanException:
            pass
