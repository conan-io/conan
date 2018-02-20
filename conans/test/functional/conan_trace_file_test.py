import unittest
from conans import tools
from conans.test.utils.test_files import temp_folder
import os
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestServer, TestClient
from conans.util.files import load
import json
from conans.paths import CONANFILE, RUN_LOG_NAME
from conans.client.runner import ConanRunner


class ConanTraceTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}

    def test_run_log_file_package_test(self):
        '''Check if the log file is generated and packaged'''

        base = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello0"
    version = "0.1"

    def build(self):
        self.run('echo "Simulating cmake..."')

    def package(self):
        self.copy(pattern="%s", dst="", keep_path=False)
    ''' % RUN_LOG_NAME

        def _install_a_package(print_commands_to_output, generate_run_log_file):

            runner = ConanRunner(print_commands_to_output, generate_run_log_file,
                                 log_run_to_output=True)

            client = TestClient(servers=self.servers,
                                users={"default": [("lasote", "mypass")]},
                                runner=runner)
            conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
            files = {}
            files[CONANFILE] = base
            client.save(files)
            client.run("user lasote -p mypass -r default")
            client.run("export . lasote/stable")
            client.run("install %s --build missing" % str(conan_reference))
            package_dir = client.client_cache.packages(ConanFileReference.loads("Hello0/0.1@lasote/stable"))
            package_dir = os.path.join(package_dir, os.listdir(package_dir)[0])
            log_file_packaged = os.path.join(package_dir, RUN_LOG_NAME)
            return log_file_packaged, client.user_io.out

        log_file_packaged, output = _install_a_package(False, True)
        self.assertIn("Copied 1 '.log' files: conan_run.log", output)
        self.assertTrue(os.path.exists(log_file_packaged))
        contents = load(log_file_packaged)
        self.assertIn("Simulating cmake...", contents)
        self.assertNotIn("----Running------%s> echo" % os.linesep, contents)

        log_file_packaged, output = _install_a_package(True, True)
        self.assertIn("Copied 1 '.log' files: conan_run.log", output)
        self.assertTrue(os.path.exists(log_file_packaged))
        contents = load(log_file_packaged)
        self.assertIn("Simulating cmake...", contents)
        self.assertIn("----Running------%s> echo" % os.linesep, contents)

        log_file_packaged, output = _install_a_package(False, False)
        self.assertNotIn("Copied 1 '.log' files: conan_run.log", output)
        self.assertFalse(os.path.exists(log_file_packaged))

    def test_trace_actions(self):
        client = TestClient(servers=self.servers,
                            users={"default": [("lasote", "mypass")]})
        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        with tools.environment_append({"CONAN_TRACE_FILE": trace_file}):
            # UPLOAD A PACKAGE
            conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
            files = cpp_hello_conan_files("Hello0", "0.1", need_patch=True, build=False)
            client.save(files)
            client.run("user lasote -p mypass -r default")
            client.run("export . lasote/stable")
            client.run("install %s --build missing" % str(conan_reference))
            client.run("upload %s --all" % str(conan_reference))

        traces = load(trace_file)
        self.assertNotIn("mypass", traces)
        self.assertIn('"password": "**********"', traces)
        self.assertIn('"Authorization": "**********"', traces)
        self.assertIn('"X-Client-Anonymous-Id": "**********"', traces)
        actions = traces.splitlines()
        self.assertEquals(len(actions), 19)
        for trace in actions:
            doc = json.loads(trace)
            self.assertIn("_action", doc)  # Valid jsons

        self.assertEquals(json.loads(actions[0])["_action"], "COMMAND")
        self.assertEquals(json.loads(actions[0])["name"], "user")

        self.assertEquals(json.loads(actions[2])["_action"], "COMMAND")
        self.assertEquals(json.loads(actions[2])["name"], "export")

        self.assertEquals(json.loads(actions[3])["_action"], "COMMAND")
        self.assertEquals(json.loads(actions[3])["name"], "install_reference")

        self.assertEquals(json.loads(actions[4])["_action"], "GOT_RECIPE_FROM_LOCAL_CACHE")
        self.assertEquals(json.loads(actions[4])["_id"], "Hello0/0.1@lasote/stable")

        self.assertEquals(json.loads(actions[-1])["_action"], "UPLOADED_PACKAGE")
