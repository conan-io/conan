import unittest

from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.graph.proxy import ConanProxy
from conans.errors import NotFoundException, ConanException
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer
from conans.client.remote_registry import RemoteRegistry


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

            def __init__(self, ok, status_code):
                self.ok = ok
                self.status_code = status_code

        class BuggyRequester(object):

            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                return Response(False, 404)

        client2 = TestClient(servers=servers, requester_class=BuggyRequester)
        conan_ref = ConanFileReference.loads("Hello/1.2.1@frodo/stable")
        registry = RemoteRegistry(client2.client_cache.registry, client2.out)
        installer = ConanProxy(client2.paths, client2.user_io.out, client2.remote_manager,
                               registry=registry)

        with self.assertRaises(NotFoundException):
            installer.get_recipe(conan_ref, False, False, None, ActionRecorder())

        class BuggyRequester2(BuggyRequester):
            def get(self, *args, **kwargs):
                return Response(False, 500)

        client2 = TestClient(servers=servers, requester_class=BuggyRequester2)
        registry = RemoteRegistry(client2.client_cache.registry, client2.out)
        installer = ConanProxy(client2.paths, client2.user_io.out, client2.remote_manager,
                               registry=registry)

        try:
            installer.get_recipe(conan_ref, False, False, None, ActionRecorder())
        except NotFoundException:
            self.assertFalse(True)  # Shouldn't capture here
        except ConanException:
            pass
