import json
import os
import sys
import unittest
from collections import OrderedDict

import pytest
import six

from conans.build_info.conan_build_info import get_build_info
from conans.client import tools
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load, save


class MyBuildInfo(unittest.TestCase):

    def setUp(self):
        test_server = TestServer(users={"lasote": "lasote"})
        test_server2 = TestServer(users={"lasote": "lasote"})
        self.servers = OrderedDict()
        self.servers["default"] = test_server
        self.servers["alternative"] = test_server2
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "lasote")],
                                                              "alternative": [("lasote", "lasote")]})

    def test_only_download(self):
        self.client.save({"conanfile.py": GenConanfile("Hello", "1.0").with_exports("*").
                         with_package_file("file", "content"),
                          "file.h": ""})
        self.client.run("export . lasote/stable")
        self.client.run("upload '*' -c --all")
        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        self.client.run("remove '*' -f")
        with tools.environment_append({"CONAN_TRACE_FILE": trace_file}):
            self.client.run("install Hello/1.0@lasote/stable --build")

        data = get_build_info(trace_file).serialize()
        self.assertEqual(len(data["modules"]), 1)
        self.assertEqual(data["modules"][0]["id"], "DownloadOnly")
        self.assertEqual(len(data["modules"][0]["artifacts"]), 0)
        self.assertEqual(len(data["modules"][0]["dependencies"]), 3)

    def test_json(self):
        # Upload to server Hello1 => Hello0 and Hello2 => Hello0
        self.client.save({"conanfile.py": GenConanfile("Hello0", "1.0").with_exports("*").
                         with_package_file("file", "content"),
                          "file.h": ""})
        self.client.run("export . lasote/stable")

        self.client.save({"conanfile.py": GenConanfile("Hello1", "1.0").
                         with_requires("Hello0/1.0@lasote/stable").with_exports("*").
                         with_package_file("file", "content")})
        self.client.run("export . lasote/stable")

        self.client.save({"conanfile.py": GenConanfile("Hello2", "1.0").with_exports("*").
                         with_package_file("file", "content").
                         with_requires("Hello0/1.0@lasote/stable")})
        self.client.run("export . lasote/stable")
        self.client.run("install Hello1/1.0@lasote/stable --build missing")
        self.client.run("install Hello2/1.0@lasote/stable --build missing")
        self.client.run("upload '*' -c --all")

        # Remove all from local cache
        self.client.run("remove '*' -f")

        # Now activate logs and install both Hello1 and Hello2
        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        with tools.environment_append({"CONAN_TRACE_FILE": trace_file}):
            self.client.run("install Hello0/1.0@lasote/stable")
            self.client.run("upload '*' -c --all")
            data = get_build_info(trace_file).serialize()
            # Only uploaded 2 modules, the Hello0 recipe and the Hello0 package
            # without dependencies
            self.assertEqual(len(data["modules"]), 2)
            self.assertEqual(len(data["modules"][0]["dependencies"]), 0)
            self.assertEqual(len(data["modules"][0]["dependencies"]), 0)
            self.assertEqual(len(data["modules"][0]["artifacts"]), 3)

            # Now upload the rest of them
            self.client.run("install Hello1/1.0@lasote/stable --build missing")
            self.client.run("install Hello2/1.0@lasote/stable --build missing")
            self.client.run("upload '*' -c --all")
            data = get_build_info(trace_file).serialize()
            self.assertEqual(len(data["modules"]), 6)
            for mod_name in ["Hello1/1.0@lasote/stable", "Hello2/1.0@lasote/stable"]:
                module = _get_module(data, mod_name)
                self.assertEqual(3, len(module["dependencies"]))
                self.assertEqual(3, len(module["artifacts"]))
                for dep in module["dependencies"]:
                    self.assertTrue(dep["id"].startswith("Hello0/1.0@lasote/stable"))

    def test_invalid_tracer(self):
        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        save(trace_file, "invalid contents")
        with six.assertRaisesRegex(self, Exception, "INVALID TRACE FILE!"):
            get_build_info(trace_file).serialize()

    def test_cross_remotes(self):

        # Upload to alternative server Hello0 but Hello1 to the default
        self.client.save({"conanfile.py": GenConanfile("Hello0", "1.0")})
        self.client.run("export . lasote/stable")

        self.client.save({"conanfile.py": GenConanfile("Hello1", "1.0").
                         with_requires("Hello0/1.0@lasote/stable")})
        self.client.run("export . lasote/stable")

        self.client.run("export . lasote/stable")
        self.client.run("install Hello1/1.0@lasote/stable --build missing")

        self.client.run("upload 'Hello0*' -c --all -r alternative")
        self.client.run("upload 'Hello1*' -c --all -r default")

        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        with tools.environment_append({"CONAN_TRACE_FILE": trace_file}):
            # Will retrieve the Hello0 deps from the alternative
            self.client.run("install Hello1/1.0@lasote/stable --build")

            # Upload to the default, not matching the Hello0 remote
            self.client.run("upload 'Hello1*' -c --all -r default")

            data = get_build_info(trace_file).serialize()
            self.assertEqual(len(data["modules"]), 2)
            module = _get_module(data, "Hello1/1.0@lasote/stable")
            self.assertEqual(0, len(module["dependencies"]))

    @pytest.mark.ide_fail
    def test_trace_command(self):
        from conans.build_info.command import run
        trace_file = os.path.join(temp_folder(), "conan_trace.log")
        # Generate some traces
        with tools.environment_append({"CONAN_TRACE_FILE": trace_file}):
            self.client.save({"conanfile.py": GenConanfile("Hello0", "1.0")})
            self.client.run("export . lasote/stable")
            self.client.run("install Hello0/1.0@lasote/stable --build")
            self.client.run("upload '*' --all -c")

        # Get json from file
        output = os.path.join(temp_folder(), "build_info.json")
        sys.argv = ['conan_build_info', trace_file, '--output', output]
        run()

        the_json = json.loads(load(output))
        self.assertTrue(the_json["modules"][0]["id"], "Hello0/1.0@lasote/stable")

        # Now get from stdout
        sys.argv = ['conan_build_info', trace_file]
        run()

        try:  # in IDEs or with --nocapture it will fail
            stdout_value = sys.stdout.getvalue()
        except AttributeError:
            pass
        else:
            the_json = json.loads(stdout_value)
            self.assertTrue(the_json["modules"][0]["id"], "Hello0/1.0@lasote/stable")


def _get_module(data, the_id):
    for module in data["modules"]:
        if module["id"] == the_id:
            return module
    return None
