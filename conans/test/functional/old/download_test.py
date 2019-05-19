import unittest

from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import Remotes
from conans.client.conan_api import Conan
from conans.client.graph.proxy import ConanProxy
from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.runner import ConanRunner
from conans.errors import ConanException, NotFoundException
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput, MockedUserIO


class DownloadTest(unittest.TestCase):

    def test_returns_on_failures(self):
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
            def get(self, *args, **kwargs):
                return Response(False, 404)

        output = TestBufferConanOutput()
        runner = ConanRunner(output=output)
        user_io = MockedUserIO({}, out=output)
        cache = ClientCache(temp_folder(), output)
        conan = Conan(cache, user_io, runner, BuggyRequester())

        ref = ConanFileReference.loads("Hello/1.2.1@frodo/stable")
        installer = ConanProxy(cache, user_io.out, conan._remote_manager)

        remotes = Remotes()
        remotes.add("remotename", "url")
        with self.assertRaises(NotFoundException):
            installer.get_recipe(ref, False, False, remotes, ActionRecorder())

        class BuggyRequester2(BuggyRequester):
            def get(self, *args, **kwargs):
                return Response(False, 500)

        conan = Conan(cache, user_io, runner, BuggyRequester2())
        installer = ConanProxy(cache, user_io.out, conan._remote_manager)

        try:
            installer.get_recipe(ref, False, False, remotes, ActionRecorder())
        except NotFoundException:
            self.assertFalse(True)  # Shouldn't capture here
        except ConanException:
            pass
