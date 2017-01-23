import unittest
from conans import tools
from conans.test.utils.test_files import temp_folder
import os
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.tools import TestServer, TestClient
from conans.util.files import load
import json


class ConanTraceTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def testTraceActions(self):
        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        with tools.environment_append({"CONAN_TRACE_FILE": trace_file}):
            # UPLOAD A PACKAGE
            conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
            files = cpp_hello_conan_files("Hello0", "0.1", need_patch=True, build=False)
            self.client.save(files)
            self.client.run("user lasote -p mypass -r default")
            self.client.run("export lasote/stable")
            self.client.run("install %s --build missing" % str(conan_reference))
            self.client.run("upload %s --all" % str(conan_reference))

        traces = load(trace_file)
        self.assertNotIn("mypass", traces)
        self.assertIn('"password": "**********"', traces)
        self.assertIn('"Authorization": "**********"', traces)
        self.assertIn('"X-Client-Anonymous-Id": "**********"', traces)
        actions = traces.splitlines()
        self.assertEquals(len(actions), 17)
        for trace in actions:
            doc = json.loads(trace)
            self.assertIn("_action", doc)  # Valid jsons

        self.assertEquals(json.loads(actions[0])["_action"], "COMMAND")
        self.assertEquals(json.loads(actions[0])["name"], "user")

        self.assertEquals(json.loads(actions[2])["_action"], "COMMAND")
        self.assertEquals(json.loads(actions[2])["name"], "export")

        self.assertEquals(json.loads(actions[3])["_action"], "COMMAND")
        self.assertEquals(json.loads(actions[3])["name"], "install")

        self.assertEquals(json.loads(actions[4])["_action"], "GOT_RECIPE_FROM_LOCAL_CACHE")
        self.assertEquals(json.loads(actions[4])["_id"], "Hello0/0.1@lasote/stable")

        self.assertEquals(json.loads(actions[-1])["_action"], "UPLOADED_PACKAGE")
