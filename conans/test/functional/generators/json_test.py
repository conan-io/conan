import json
import os
import unittest

from conans.client.generators.json_generator import JsonGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.tools import TestClient


class JsonTest(unittest.TestCase):

    def generate_json_info_test(self):
        conanfile_py = """from conans import ConanFile

class HelloConan(ConanFile):
    exports_sources = "*.h"
    def package(self):
        self.copy("*.h", dst="include")
    def package_info(self):
        self.env_info.MY_ENV_VAR = "foo"
        self.user_info.my_var = "my_value"
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile_py,
                     "header.h": ""})
        client.run("create . Hello/0.1@lasote/testing")
        client.run("install Hello/0.1@lasote/testing -g json")
        conan_json = os.path.join(client.current_folder, "conanbuildinfo.json")
        with open(conan_json) as f:
            data = json.load(f)
        self.assertEquals(data["deps_env_info"]["MY_ENV_VAR"], "foo")
        self.assertEquals(data["deps_user_info"]["Hello"]["my_var"], "my_value")
        hello_data = data["dependencies"][0]
        self.assertTrue(os.path.exists(hello_data["rootpath"]))
        include_path = hello_data["include_paths"][0]
        self.assertTrue(os.path.isabs(include_path))
        self.assertTrue(os.path.exists(include_path))

    def generate_json_info_settings_test(self):
        conanfile_py = """from conans import ConanFile

class HelloConan(ConanFile):
    exports_sources = "*.h"
    settings = "os", "arch"
    def package(self):
        self.copy("*.h", dst="include")
    def package_info(self):
        self.env_info.MY_ENV_VAR = "foo"
        self.user_info.my_var = "my_value"
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile_py,
                     "header.h": ""})
        settings = "-sos=Linux -sarch=x86_64"
        client.run("create . Hello/0.1@lasote/testing " + settings)
        client.run("install Hello/0.1@lasote/testing -g json " + settings)
        conan_json = os.path.join(client.current_folder, "conanbuildinfo.json")
        with open(conan_json) as f:
            data = json.load(f)
        settings_data = data["settings"]
        self.assertEqual(settings_data["os"], "Linux")
        self.assertEqual(settings_data["arch"], "x86_64")
