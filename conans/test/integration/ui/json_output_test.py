import json
import os
import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import save


@pytest.mark.xfail(reason="JSon output to be revisited, because based on ActionRecorder")
class JsonOutputTest(unittest.TestCase):

    def setUp(self):
        self.servers = {"default": TestServer()}
        self.client = TestClient(servers=self.servers)

    def test_simple_fields(self):
        # Result of a create
        self.client.save({"conanfile.py": GenConanfile("cc", "1.0")}, clean_first=True)
        self.client.run("create . private_user/channel --json=myfile.json")
        my_json = json.loads(self.client.load("myfile.json"))
        self.assertFalse(my_json["error"])
        tmp = RecipeReference.loads(my_json["installed"][0]["recipe"]["id"])
        self.assertEqual(str(tmp), "cc/1.0@private_user/channel")
        self.assertIsNotNone(tmp.revision)
        self.assertFalse(my_json["installed"][0]["recipe"]["dependency"])
        self.assertTrue(my_json["installed"][0]["recipe"]["exported"])
        self.assertFalse(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertIsNone(my_json["installed"][0]["recipe"]["remote"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["built"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["cpp_info"])

        # Result of an install retrieving only the recipe
        self.client.run("upload cc/1.0@private_user/channel -c -r default")
        self.client.run("remove '*' -f")
        self.client.run("install --reference=c/1.0@private_user/channel --json=myfile.json --build missing ")
        my_json = json.loads(self.client.load("myfile.json"))

        the_time_str = my_json["installed"][0]["recipe"]["time"]
        self.assertIn("T", the_time_str)  # Weak validation of the ISO 8601
        self.assertFalse(my_json["error"])
        self.assertEqual(my_json["installed"][0]["recipe"]["id"], "cc/1.0@private_user/channel")
        self.assertTrue(my_json["installed"][0]["recipe"]["dependency"])
        self.assertTrue(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertIsNotNone(my_json["installed"][0]["recipe"]["remote"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["built"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["cpp_info"])

        # Upload the binary too
        self.client.run("upload cc/1.0@private_user/channel --all -c -r default")
        self.client.run("remove '*' -f")
        self.client.run("install --reference=c/1.0@private_user/channel --json=myfile.json")
        my_json = json.loads(self.client.load("myfile.json"))

        self.assertFalse(my_json["error"])
        self.assertEqual(my_json["installed"][0]["recipe"]["id"], "cc/1.0@private_user/channel")
        self.assertTrue(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertIsNotNone(my_json["installed"][0]["recipe"]["remote"])
        self.assertFalse(my_json["installed"][0]["packages"][0]["built"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["downloaded"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["cpp_info"])

        # Force build
        self.client.run("remove '*' -f")
        self.client.run("install --reference=cc/1.0@private_user/channel --json=myfile.json --build")
        my_json = json.loads(self.client.load("myfile.json"))

        self.assertFalse(my_json["error"])
        self.assertEqual(my_json["installed"][0]["recipe"]["id"], "cc/1.0@private_user/channel")
        self.assertTrue(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertIsNotNone(my_json["installed"][0]["recipe"]["remote"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["built"])
        self.assertFalse(my_json["installed"][0]["packages"][0]["downloaded"])
        self.assertTrue(my_json["installed"][0]["packages"][0]["cpp_info"])

    def test_errors(self):

        # Missing recipe
        self.client.run("install --reference=cc/1.0@private_user/channel --json=myfile.json", assert_error=True)
        my_json = json.loads(self.client.load("myfile.json"))
        self.assertTrue(my_json["error"])
        self.assertEqual(len(my_json["installed"]), 1)
        self.assertFalse(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertEqual(my_json["installed"][0]["recipe"]["error"],
                         {'type': 'missing', 'remote': None,
                          'description': "Unable to find 'c/1.0@private_user/channel' in remotes"})

        # Missing binary package
        self.client.save({"conanfile.py": GenConanfile("c", "1.0")}, clean_first=True)
        self.client.run("create . private_user/channel --json=myfile.json ")
        self.client.run("upload c/1.0@private_user/channel -c -r default")
        self.client.run("remove '*' -f")
        self.client.run("install --reference=c/1.0@private_user/channel --json=myfile.json", assert_error=True)
        my_json = json.loads(self.client.load("myfile.json"))

        self.assertTrue(my_json["error"])
        self.assertEqual(len(my_json["installed"]), 1)
        self.assertTrue(my_json["installed"][0]["recipe"]["downloaded"])
        self.assertFalse(my_json["installed"][0]["recipe"]["error"])
        self.assertEqual(len(my_json["installed"][0]["packages"]), 1)
        self.assertFalse(my_json["installed"][0]["packages"][0]["downloaded"])
        self.assertEqual(my_json["installed"][0]["packages"][0]["error"]["type"], "missing")
        self.assertIsNone(my_json["installed"][0]["packages"][0]["error"]["remote"])
        self.assertIn("Can't find a 'c/1.0@private_user/channel' package",
                      my_json["installed"][0]["packages"][0]["error"]["description"])

        # Error building
        conanfile = str(GenConanfile("c", "1.0")) + """
    def build(self):
        raise Exception("Build error!")
        """
        self.client.save({"conanfile.py": conanfile}, clean_first=True)
        self.client.run("create . private_user/channel --json=myfile.json ", assert_error=True)
        my_json = json.loads(self.client.load("myfile.json"))
        self.assertTrue(my_json["error"])
        self.assertEqual(my_json["installed"][0]["packages"][0]["error"]["type"], "building")
        self.assertIsNone(my_json["installed"][0]["packages"][0]["error"]["remote"])
        self.assertIn("c/1.0@private_user/channel: Error in build() method, line 6",
                      my_json["installed"][0]["packages"][0]["error"]["description"])

    def test_json_generation(self):

        self.client.save({"conanfile.py": GenConanfile("c", "1.0").
                         with_option("static", [True, False]).with_default_option("static", True)},
                         clean_first=True)
        self.client.run("create . private_user/channel --json=myfile.json ")

        self.client.run('upload "*" -c --all -r default')

        conanfile = str(GenConanfile("BB", "1.0")) + """
    def configure(self):
        self.options["c"].static = False

    def build_requirements(self):
        self.build_requires("c/1.0@private_user/channel")
"""
        self.client.save({"conanfile.py": conanfile}, clean_first=True)
        self.client.run("create . private_user/channel --build missing")
        self.client.run('upload "*" -c --all -r default')

        self.client.save({"conanfile.py": GenConanfile("AA", "1.0").
                         with_require("BB/1.0@private_user/channel")},
                         clean_first=True)
        self.client.run("create . private_user/channel")
        self.client.run('upload "*" -c --all -r default')

        save(os.path.join(self.client.cache.profiles_path, "mybr"),
             """
include(default)
[tool_requires]
AA*: c/1.0@private_user/channel
""")
        self.client.save({"conanfile.py": GenConanfile("PROJECT", "1.0").
                         with_require("AA/1.0@private_user/channel")}, clean_first=True)
        self.client.run("install . --profile mybr --json=myfile.json --build AA --build BB")
        my_json = self.client.load("myfile.json")
        my_json = json.loads(my_json)

        self.assertTrue(my_json["installed"][0]["recipe"]["dependency"])
        self.assertTrue(my_json["installed"][1]["recipe"]["dependency"])
        self.assertTrue(my_json["installed"][2]["recipe"]["dependency"])

        # Installed the build require c with two options
        self.assertEqual(len(my_json["installed"][2]["packages"]), 2)
        tmp = RecipeReference.loads(my_json["installed"][2]["recipe"]["id"])
        self.assertIsNotNone(tmp.revision)
        self.assertEqual(str(tmp), "c/1.0@private_user/channel")
        self.assertFalse(my_json["installed"][2]["recipe"]["downloaded"])
        self.assertFalse(my_json["installed"][2]["packages"][0]["downloaded"])
        self.assertFalse(my_json["installed"][2]["packages"][1]["downloaded"])

    def test_json_create_multiconfig(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                def package_info(self):
                    self.cpp_info.release.libs = ["hello"]
                    self.cpp_info.debug.libs = ["hello_d"]

                    self.cpp_info.debug.libdirs = ["lib-debug"]

            """)
        self.client.save({'conanfile.py': conanfile})
        self.client.run("create . name/version@user/channel --json=myfile.json")
        my_json = self.client.load("myfile.json")
        my_json = json.loads(my_json)

        # Nodes with cpp_info
        cpp_info = my_json["installed"][0]["packages"][0]["cpp_info"]
        cpp_info_debug = cpp_info["configs"]["debug"]
        cpp_info_release = cpp_info["configs"]["release"]

        # Each node should have its own information
        self.assertFalse("libs" in cpp_info)
        self.assertEqual(cpp_info_debug["libs"], ["hello_d"])
        self.assertEqual(cpp_info_release["libs"], ["hello"])
        self.assertEqual(cpp_info_debug["libdirs"], ["lib-debug"])
        self.assertEqual(cpp_info_release["libdirs"], [DEFAULT_LIB])

        # FIXME: There are _empty_ nodes
        self.assertEqual(cpp_info_debug["builddirs"], [""])
        self.assertEqual(cpp_info_release["builddirs"], [""])

        # FIXME: Default information is duplicated in all the nodes
        dupe_nodes = ["rootpath", "includedirs", "resdirs",
                      "bindirs", "builddirs", "filter_empty"]
        for dupe in dupe_nodes:
            self.assertEqual(cpp_info[dupe], cpp_info_debug[dupe])
            self.assertEqual(cpp_info[dupe], cpp_info_release[dupe])
