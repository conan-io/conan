import os
import json
import unittest
from conans.test.utils.tools import TestClient

conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def package_info(self):
        self.env_info.MY_ENV_VAR = "foo"
        self.user_info.my_var = "my_value"

"""

conanfile = """[requires]
Hello/0.1@lasote/testing
"""

cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)
"""


class JsonGeneratorTest(unittest.TestCase):
    def generate_json_info_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export . lasote/testing")
        client.save({"conanfile.txt": conanfile, "CMakeLists.txt": cmake}, clean_first=True)
        client.run("install . -g json --build")
        conan_json = os.path.join(client.current_folder, "conanbuildinfo.json")
        with open(conan_json) as f:
            data = json.load(f)
        self.assertEquals(data["deps_env_info"]["MY_ENV_VAR"], "foo")
        self.assertEquals(data["deps_user_info"]["Hello"]["my_var"], "my_value")
        hello_data = data["dependencies"][0]
        self.assertTrue(os.path.exists(hello_data["rootpath"]))
