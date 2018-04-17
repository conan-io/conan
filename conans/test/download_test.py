import unittest

from conans.client.action_recorder import ActionRecorder
from conans.client.proxy import ConanProxy
from conans.errors import NotFoundException, ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, TestServer


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
        package_ref = PackageReference(conan_ref, "123123123")
        installer = ConanProxy(client2.paths, client2.user_io, client2.remote_manager,
                               "default", recorder=ActionRecorder())
        package_folder = client2.client_cache.package(package_ref)

        with self.assertRaises(NotFoundException):
            installer.get_recipe(conan_ref)

        self.assertFalse(installer.package_available(package_ref, package_folder, True))

        class BuggyRequester2(BuggyRequester):
            def get(self, *args, **kwargs):
                return Response(False, 500)

        client2 = TestClient(servers=servers, requester_class=BuggyRequester2)
        installer = ConanProxy(client2.paths, client2.user_io, client2.remote_manager, "default",
                               recorder=ActionRecorder())

        try:
            installer.get_recipe(conan_ref)
        except NotFoundException:
            self.assertFalse(True)  # Shouldn't capture here
        except ConanException:
            pass

        try:
            installer.package_available(package_ref, package_folder, True)
        except NotFoundException:
            self.assertFalse(True)  # Shouldn't capture here
        except ConanException:
            pass
