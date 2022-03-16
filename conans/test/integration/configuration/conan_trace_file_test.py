import json
import os

import unittest

import pytest

from conans.model.recipe_ref import RecipeReference

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer
from conans.util.env import environment_update
from conans.util.files import load


class ConanTraceTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer(users={"lasote": "mypass"})
        self.servers = {"default": test_server}

    @pytest.mark.xfail(reason="We are passing Profile in the API that's not serializable")
    def test_trace_actions(self):
        client = TestClient(servers=self.servers)
        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        with environment_update({"CONAN_TRACE_FILE": trace_file}):
            # UPLOAD A PACKAGE
            ref = RecipeReference.loads("hello0/0.1@lasote/stable")
            client.save({"conanfile.py": GenConanfile("hello0", "0.1").with_exports("*"),
                         "file.txt": "content"})
            client.run("remote login default lasote -p mypass")
            client.run("export . --user=lasote --channel=stable")
            client.run("install --requires=%s --build missing" % str(ref))
            client.run("upload %s -r default" % str(ref))

        traces = load(trace_file)
        self.assertNotIn("mypass", traces)
        self.assertIn('"password": "**********"', traces)
        self.assertIn('"Authorization": "**********"', traces)
        self.assertIn('"X-Client-Anonymous-Id": "**********"', traces)
        actions = traces.splitlines()
        num_put = len([it for it in actions if "REST_API_CALL" in it and "PUT" in it])
        self.assertEqual(num_put, 6)   # 3 files the recipe 3 files the package

        num_post = len([it for it in actions if "REST_API_CALL" in it and "POST" in it])
        if "/v2/" in traces:
            self.assertEqual(num_post, 0)
        else:
            self.assertEqual(num_post, 2)  # 2 get urls

        num_get = len([it for it in actions if "REST_API_CALL" in it and "GET" in it])
        self.assertEqual(num_get, 8)

        # Check masked signature
        for action in actions:
            doc = json.loads(action)
            if doc.get("url") and "signature" in doc.get("url"):
                self.assertIn("signature=*****", doc.get("url"))
