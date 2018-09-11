import json
import os
import unittest

from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestServer, TestClient
from conans.util.files import save, load


class JsonOutputTest(unittest.TestCase):

    def setUp(self):
        self.servers = {"default": TestServer()}
        self.client = TestClient(servers=self.servers)

    def test_simple_fields(self):
        # Result of a create
        files = cpp_hello_conan_files("CC", "1.0", build=False)
        self.client.save(files, clean_first=True)
        self.client.run("create . private_user/channel --json=myfile.json ")
        my_json = json.loads(load(os.path.join(self.client.current_folder, "myfile.json")))
        self.assertFalse(my_json["error"])
        self.assertEquals(my_json["installed"][0]["recipe"]["id"], "CC/1.0@private_user/channel")
        self.assertFalse(my_json["installed"][0]["recipe"]["dependency"])
        self.assertTrue(my_json["installed"][0]["recipe"]["cache"])
        self.assertIsNone(my_json["installed"][0]["recipe"]["remote"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["built"])

        # Result of an install retrieving only the recipe
        self.client.run("upload CC/1.0@private_user/channel -c")
        self.client.run("remove '*' -f")
        self.client.run("install CC/1.0@private_user/channel --json=myfile.json --build missing ")
        my_json = json.loads(load(os.path.join(self.client.current_folder, "myfile.json")))

        the_time_str = my_json["installed"][0]["recipe"]["time"]
        self.assertIn("T", the_time_str) # Weak validation of the ISO 8601
        self.assertFalse(my_json["error"])
        self.assertEquals(my_json["installed"][0]["recipe"]["id"], "CC/1.0@private_user/channel")
        self.assertTrue(my_json["installed"][0]["recipe"]["dependency"])
        self.assertFalse(my_json["installed"][0]["recipe"]["cache"])
        self.assertTrue(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertIsNotNone(my_json["installed"][0]["recipe"]["remote"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["built"])

        # Upload the binary too
        self.client.run("upload CC/1.0@private_user/channel --all -c")
        self.client.run("remove '*' -f")
        self.client.run("install CC/1.0@private_user/channel --json=myfile.json")
        my_json = json.loads(load(os.path.join(self.client.current_folder, "myfile.json")))

        self.assertFalse(my_json["error"])
        self.assertEquals(my_json["installed"][0]["recipe"]["id"], "CC/1.0@private_user/channel")
        self.assertFalse(my_json["installed"][0]["recipe"]["cache"])
        self.assertTrue(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertIsNotNone(my_json["installed"][0]["recipe"]["remote"])
        self.assertFalse(my_json["installed"][0]["packages"][0]["built"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["downloaded"])

        # Force build
        self.client.run("remove '*' -f")
        self.client.run("install CC/1.0@private_user/channel --json=myfile.json --build")
        my_json = json.loads(load(os.path.join(self.client.current_folder, "myfile.json")))

        self.assertFalse(my_json["error"])
        self.assertEquals(my_json["installed"][0]["recipe"]["id"], "CC/1.0@private_user/channel")
        self.assertFalse(my_json["installed"][0]["recipe"]["cache"])
        self.assertTrue(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertIsNotNone(my_json["installed"][0]["recipe"]["remote"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["built"])
        self.assertFalse(my_json["installed"][0]["packages"][0]["downloaded"])

    def test_errors(self):

        # Missing recipe
        error = self.client.run("install CC/1.0@private_user/channel --json=myfile.json",
                                ignore_error=True)
        self.assertTrue(error)
        my_json = json.loads(load(os.path.join(self.client.current_folder, "myfile.json")))
        self.assertTrue(my_json["error"])
        self.assertEquals(len(my_json["installed"]), 1)
        self.assertFalse(my_json["installed"][0]["recipe"]["cache"])
        self.assertFalse(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertEquals(my_json["installed"][0]["recipe"]["error"],
                          {'type': 'missing', 'remote': None,
                          'description': "Unable to find 'CC/1.0@private_user/channel' in remotes"})

        # Missing binary package
        files = cpp_hello_conan_files("CC", "1.0", build=False)
        self.client.save(files, clean_first=True)
        self.client.run("create . private_user/channel --json=myfile.json ")
        self.client.run("upload CC/1.0@private_user/channel -c")
        self.client.run("remove '*' -f")
        error = self.client.run("install CC/1.0@private_user/channel --json=myfile.json",
                                ignore_error=True)
        my_json = json.loads(load(os.path.join(self.client.current_folder, "myfile.json")))

        self.assertTrue(error)
        self.assertTrue(my_json["error"])
        self.assertEquals(len(my_json["installed"]), 1)
        self.assertFalse(my_json["installed"][0]["recipe"]["cache"])
        self.assertTrue(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertFalse(my_json["installed"][0]["recipe"]["error"])
        self.assertEquals(len(my_json["installed"][0]["packages"]), 1)
        self.assertFalse(my_json["installed"][0]["packages"][0]["cache"])
        self.assertFalse(my_json["installed"][0]["packages"][0]["downloaded"])
        self.assertEquals(my_json["installed"][0]["packages"][0]["error"]["type"], "missing")
        self.assertIsNone(my_json["installed"][0]["packages"][0]["error"]["remote"])
        self.assertIn("Can't find a 'CC/1.0@private_user/channel' package",
                      my_json["installed"][0]["packages"][0]["error"]["description"])

        # Error building
        files["conanfile.py"] = files["conanfile.py"].replace("def build2(self):",
                                                              """
    def build(self):
        raise Exception("Build error!")
        """)

        self.client.save(files, clean_first=True)
        self.client.run("create . private_user/channel --json=myfile.json ", ignore_error=True)
        my_json = json.loads(load(os.path.join(self.client.current_folder, "myfile.json")))
        self.assertTrue(my_json["error"])
        self.assertEquals(my_json["installed"][0]["packages"][0]["error"]["type"], "building")
        self.assertIsNone(my_json["installed"][0]["packages"][0]["error"]["remote"])
        self.assertIn("CC/1.0@private_user/channel: Error in build() method, line 36",
                      my_json["installed"][0]["packages"][0]["error"]["description"])

    def test_json_generation(self):

        files = cpp_hello_conan_files("CC", "1.0", build=False)
        self.client.save(files, clean_first=True)
        self.client.run("create . private_user/channel --json=myfile.json ")

        self.client.run('upload "*" -c --all')

        files = cpp_hello_conan_files("BB", "1.0", build=False)
        files["conanfile.py"] += """
    def configure(self):
        self.options["CC"].static = False

    def build_requirements(self):
        self.build_requires("CC/1.0@private_user/channel")

"""
        self.client.save(files, clean_first=True)
        self.client.run("create . private_user/channel --build missing")
        self.client.run('upload "*" -c --all')

        files = cpp_hello_conan_files("AA", "1.0",
                                      deps=["BB/1.0@private_user/channel"], build=False)
        self.client.save(files, clean_first=True)
        self.client.run("create . private_user/channel")
        self.client.run('upload "*" -c --all')

        save(os.path.join(self.client.client_cache.profiles_path, "mybr"),
             """
include(default)
[build_requires]
AA*: CC/1.0@private_user/channel
""")
        files = cpp_hello_conan_files("PROJECT", "1.0",
                                      deps=["AA/1.0@private_user/channel"], build=False)
        self.client.save(files, clean_first=True)
        self.client.run("install . --profile mybr --json=myfile.json --build AA --build BB")
        my_json = load(os.path.join(self.client.current_folder, "myfile.json"))
        my_json = json.loads(my_json)

        self.assertTrue(my_json["installed"][0]["recipe"]["dependency"])
        self.assertTrue(my_json["installed"][1]["recipe"]["dependency"])
        self.assertTrue(my_json["installed"][2]["recipe"]["dependency"])

        # Installed the build require CC with two options
        self.assertEquals(len(my_json["installed"][2]["packages"]), 2)
        self.assertEquals(my_json["installed"][2]["recipe"]["id"], "CC/1.0@private_user/channel")
        self.assertTrue(my_json["installed"][2]["recipe"]["cache"])
        self.assertTrue(my_json["installed"][2]["packages"][0]["cache"])
        self.assertTrue(my_json["installed"][2]["packages"][1]["cache"])
