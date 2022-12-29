import json
import os
import textwrap
import unittest


from conans.client import tools
from conans.client.runner import ConanRunner
from conans.model.ref import ConanFileReference
from conans.paths import RUN_LOG_NAME
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import load


class ConanTraceTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}

    def test_run_log_file_packaged(self):
        """Check if the log file is generated and packaged"""

        base = textwrap.dedent("""
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "Hello0"
                version = "0.1"

                def build(self):
                    self.run('echo "Simulating cmake..."')

                def package(self):
                    self.copy(pattern="%s", dst="", keep_path=False)
            """ % RUN_LOG_NAME)

        def _install_a_package(print_commands_to_output, generate_run_log_file):
            out = TestBufferConanOutput()
            runner = ConanRunner(print_commands_to_output, generate_run_log_file,
                                 log_run_to_output=True, output=out)

            client = TestClient(servers=self.servers,
                                users={"default": [("lasote", "mypass")]},
                                runner=runner)
            ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
            client.save({"conanfile.py": base})
            client.run("create . lasote/stable")
            package_dir = client.cache.package_layout(ref).packages()
            package_dir = os.path.join(package_dir, os.listdir(package_dir)[0])
            log_file_packaged_ = os.path.join(package_dir, RUN_LOG_NAME)
            out = "\n".join([str(out), str(client.out)])
            return log_file_packaged_, out

        log_file_packaged, output = _install_a_package(False, True)
        self.assertIn("Packaged 1 '.log' file: conan_run.log", output)
        self.assertTrue(os.path.exists(log_file_packaged))
        contents = load(log_file_packaged)
        self.assertIn("Simulating cmake...", contents)
        self.assertNotIn("----Running------%s> echo" % os.linesep, contents)

        log_file_packaged, output = _install_a_package(True, True)
        self.assertIn("Packaged 1 '.log' file: conan_run.log", output)
        self.assertTrue(os.path.exists(log_file_packaged))
        contents = load(log_file_packaged)
        self.assertIn("Simulating cmake...", contents)
        self.assertIn("----Running------%s> echo" % os.linesep, contents)

        log_file_packaged, output = _install_a_package(False, False)
        self.assertNotIn("Packaged 1 '.log' file: conan_run.log", output)
        self.assertFalse(os.path.exists(log_file_packaged))

    def test_trace_actions(self):
        client = TestClient(servers=self.servers,
                            users={"default": [("lasote", "mypass")]})
        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        with tools.environment_append({"CONAN_TRACE_FILE": trace_file}):
            # UPLOAD A PACKAGE
            ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
            client.save({"conanfile.py": GenConanfile("Hello0", "0.1").with_exports("*"),
                         "file.txt": "content"})
            client.run("user lasote -p mypass -r default")
            client.run("export . lasote/stable")
            client.run("install %s --build missing" % str(ref))
            client.run("upload %s --all" % str(ref))

        traces = load(trace_file)
        self.assertNotIn("mypass", traces)
        self.assertIn('"password": "**********"', traces)
        self.assertIn('"Authorization": "**********"', traces)
        self.assertIn('"X-Client-Anonymous-Id": "**********"', traces)
        actions = traces.splitlines()
        without_rest_api = [it for it in actions if "REST_API_CALL" not in it]
        assert len(without_rest_api) == 11
        for trace in actions:
            doc = json.loads(trace)
            self.assertIn("_action", doc)  # Valid jsons

        print(without_rest_api)
        self.assertEqual(json.loads(without_rest_api[0])["_action"], "COMMAND")
        self.assertEqual(json.loads(without_rest_api[0])["name"], "authenticate")
        self.assertEqual(json.loads(without_rest_api[2])["_action"], "COMMAND")
        self.assertEqual(json.loads(without_rest_api[2])["name"], "export")
        self.assertEqual(json.loads(without_rest_api[3])["_action"], "COMMAND")
        self.assertEqual(json.loads(without_rest_api[3])["name"], "install_reference")
        self.assertEqual(json.loads(without_rest_api[4])["_action"], "GOT_RECIPE_FROM_LOCAL_CACHE")
        self.assertEqual(json.loads(without_rest_api[4])["_id"], "Hello0/0.1@lasote/stable")
        self.assertEqual(json.loads(without_rest_api[5])["_action"], "PACKAGE_BUILT_FROM_SOURCES")
        self.assertEqual(json.loads(without_rest_api[6])["_action"], "COMMAND")
        self.assertEqual(json.loads(without_rest_api[6])["name"], "upload")
        self.assertEqual(json.loads(without_rest_api[7])["_action"], "ZIP")
        self.assertEqual(json.loads(without_rest_api[8])["_action"], "UPLOADED_RECIPE")
        self.assertEqual(json.loads(without_rest_api[9])["_action"], "ZIP")
        self.assertEqual(json.loads(without_rest_api[10])["_action"], "UPLOADED_PACKAGE")

        num_put = len([it for it in actions if "REST_API_CALL" in it and "PUT" in it])
        self.assertEqual(num_put, 6)   # 3 files the recipe 3 files the package

        num_post = len([it for it in actions if "REST_API_CALL" in it and "POST" in it])
        if "/v2/" in traces:
            self.assertEqual(num_post, 0)
        else:
            self.assertEqual(num_post, 2)  # 2 get urls

        num_get = len([it for it in actions if "REST_API_CALL" in it and "GET" in it])
        self.assertEqual(num_get, 10)

        # Check masked signature
        for action in actions:
            doc = json.loads(action)
            if doc.get("url") and "signature" in doc.get("url"):
                self.assertIn("signature=*****", doc.get("url"))
