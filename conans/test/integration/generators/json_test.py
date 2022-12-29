import json
import os
import textwrap
import unittest

from conans.test.utils.tools import TestClient


class JsonTest(unittest.TestCase):

    def test_generate_json_info(self):
        conanfile_py = """from conans import ConanFile

class HelloConan(ConanFile):
    exports_sources = "*.h"
    description = "my desc"
    def layout(self):
        pass
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
        conan_json = client.load("conanbuildinfo.json")
        data = json.loads(conan_json)
        self.assertEqual(data["dependencies"][0]["version"], "0.1")
        self.assertEqual(data["dependencies"][0]["description"], "my desc")
        self.assertEqual(data["deps_env_info"]["MY_ENV_VAR"], "foo")
        self.assertEqual(data["deps_user_info"]["Hello"]["my_var"], "my_value")

        hello_data = data["dependencies"][0]
        self.assertTrue(os.path.exists(hello_data["rootpath"]))
        include_path = hello_data["include_paths"][0]
        self.assertTrue(os.path.isabs(include_path))
        self.assertTrue(os.path.exists(include_path))

    def test_generate_json_info_settings(self):
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

        conan_json = client.load("conanbuildinfo.json")
        data = json.loads(conan_json)
        settings_data = data["settings"]

        self.assertEqual(settings_data["os"], "Linux")
        self.assertEqual(settings_data["arch"], "x86_64")

    def test_multiconfig(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                settings = "os", "arch"
                generators = "json"

                def package_info(self):
                    self.env_info.MY_ENV_VAR = "foo"
                    self.user_info.my_var = "my_value"

                    self.cpp_info.debug.defines = ["LIB_DEBUG"]
                    self.cpp_info.release.defines = ["LIB_RELEASE"]

                    self.cpp_info.debug.libs = ["Hello_d"]
                    self.cpp_info.release.libs = ["Hello"]
            """)
        client = TestClient()
        client.save({'conanfile.py': conanfile})

        client.run("create . Hello/0.1@lasote/testing")
        client.run("install Hello/0.1@lasote/testing -g json")

        my_json = json.loads(client.load("conanbuildinfo.json"))

        # Nodes with cpp_info
        deps_info = my_json["dependencies"][0]
        deps_info_debug = deps_info["configs"]["debug"]
        deps_info_release = deps_info["configs"]["release"]

        # Each node should have its own information
        self.assertListEqual(deps_info["defines"], [])
        self.assertEqual(deps_info_debug["defines"], ["LIB_DEBUG"])
        self.assertEqual(deps_info_release["defines"], ["LIB_RELEASE"])

        self.assertListEqual(deps_info["libs"], [])
        self.assertEqual(deps_info_debug["libs"], ["Hello_d"])
        self.assertEqual(deps_info_release["libs"], ["Hello"])

        # FIXME: There are _null_ nodes
        self.assertEqual(deps_info_debug["description"], None)
        self.assertEqual(deps_info_release["description"], None)

        # FIXME: Empty (and rootpath) information is duplicated in all the nodes
        dupe_nodes = ["rootpath", "sysroot", "include_paths", "lib_paths", "bin_paths",
                      "build_paths", "res_paths", "cflags", "cppflags", "sharedlinkflags",
                      "exelinkflags"]
        for dupe in dupe_nodes:
            self.assertEqual(deps_info[dupe], deps_info_debug[dupe])
            self.assertEqual(deps_info[dupe], deps_info_release[dupe])

    def test_system_libs(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                settings = "os", "arch"
                generators = "json"

                def package_info(self):
                    self.cpp_info.libs = ["LIB1"]
                    self.cpp_info.system_libs = ["SYSTEM_LIB1"]
            """)
        client = TestClient()
        client.save({'conanfile.py': conanfile})

        client.run("create . Hello/0.1@lasote/testing")
        client.run("install Hello/0.1@lasote/testing -g json")

        my_json = client.load("conanbuildinfo.json")
        my_json = json.loads(my_json)
        self.assertListEqual(my_json["dependencies"][0]["libs"], ["LIB1"])
        self.assertListEqual(my_json["dependencies"][0]["system_libs"], ["SYSTEM_LIB1"])

    def test_generate_json_filenames(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class HelloConan(ConanFile):
                def package_info(self):
                    self.cpp_info.filenames['cmake_find_package'] = 'FooBar'
                    self.cpp_info.names['cmake_find_package'] = 'foobar'
                    self.cpp_info.names['cmake_find_package_multi'] = 'foobar_multi'
                    self.cpp_info.names['pkg_config'] = 'foobar_cfg'
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . bar/0.1.0@user/testing")
        client.run("install bar/0.1.0@user/testing -g json")
        conan_json = client.load("conanbuildinfo.json")
        content = json.loads(conan_json)

        deps = content["dependencies"][0]
        self.assertEqual("foobar", deps["names"]["cmake_find_package"])
        self.assertEqual("foobar_multi", deps["names"]["cmake_find_package_multi"])
        self.assertEqual("foobar_cfg", deps["names"]["pkg_config"])
        self.assertEqual("FooBar", deps["filenames"]["cmake_find_package"])
        self.assertEqual("bar", deps["name"])
