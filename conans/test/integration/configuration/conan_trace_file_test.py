import json
import os
import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference

from conans.paths import RUN_LOG_NAME
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer
from conans.util.env import environment_update
from conans.util.files import load


class ConanTraceTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer(users={"lasote": "mypass"})
        self.servers = {"default": test_server}

    def test_run_log_file_packaged(self):
        """Check if the log file is generated and packaged"""

        base = textwrap.dedent("""
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "hello0"
                version = "0.1"

                def build(self):
                    self.run('echo "Simulating cmake..."')

                def package(self):
                    self.copy(pattern="%s", dst="", keep_path=False)
            """ % RUN_LOG_NAME)

        def _install_a_package(print_commands_to_output, generate_run_log_file):
            client = TestClient(servers=self.servers)
            conan_conf = textwrap.dedent("""
                                        [storage]
                                        path = ./data
                                        [log]
                                        print_run_commands={}
                                        run_to_file={}
                                        run_to_output=True
                                    """.format(print_commands_to_output, generate_run_log_file))
            client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
            ref = RecipeReference.loads("hello0/0.1@lasote/stable")
            client.save({"conanfile.py": base})
            client.run("create . lasote/stable")
            pref = client.get_latest_package_reference(ref)
            package_dir = client.get_latest_pkg_layout(pref).package()
            log_file_packaged_ = os.path.join(package_dir, RUN_LOG_NAME)
            out = "\n".join([str(client.out), str(client.out)])
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
            client.run("install --reference=%s --build missing" % str(ref))
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
