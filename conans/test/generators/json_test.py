import json
import unittest
import os

from conans.client.generators.json_generator import JsonGenerator
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.model.env_info import EnvValues


class JsonTest(unittest.TestCase):

    def variables_setup_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"

        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cppflags = ["-cppflag"]
        cpp_info.public_deps = ["MyPkg"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = JsonGenerator(conanfile)
        json_out = generator.content

        parsed = json.loads(json_out)
        dependencies = parsed["dependencies"]
        self.assertEquals(len(dependencies), 2)
        my_pkg = dependencies[0]
        self.assertEquals(my_pkg["name"], "MyPkg")
        self.assertEquals(my_pkg["description"], "My cool description")
        self.assertEquals(my_pkg["defines"], ["MYDEFINE1"])

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
