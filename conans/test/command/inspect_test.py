import os
import unittest

from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load
import json


class ConanInspectTest(unittest.TestCase):

    def python_requires_test(self):
        server = TestServer()
        client = TestClient(servers={"default": server}, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    _my_var = 123
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . Base/0.1@lasote/testing")
        conanfile = """from conans import python_requires
base = python_requires("Base/0.1@lasote/testing")
class Pkg(base.Pkg):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("inspect Pkg/0.1@lasote/testing -a=_my_var -r=default")
        self.assertIn("_my_var: 123", client.out)
        # Inspect fetch recipes into local cache
        client.run("search")
        self.assertIn("Base/0.1@lasote/testing", client.out)
        self.assertIn("Pkg/0.1@lasote/testing", client.out)

    def name_version_test(self):
        server = TestServer()
        client = TestClient(servers={"default": server}, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "MyPkg"
    version = "1.2.3"
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect . -a=name")
        self.assertIn("name: MyPkg", client.out)
        client.run("inspect . -a=version")
        self.assertIn("version: 1.2.3", client.out)
        client.run("inspect . -a=version -a=name")
        self.assertIn("name: MyPkg", client.out)
        self.assertIn("version: 1.2.3", client.out)
        client.run("inspect . -a=version -a=name --json=file.json")
        contents = load(os.path.join(client.current_folder, "file.json"))
        self.assertIn('"version": "1.2.3"', contents)
        self.assertIn('"name": "MyPkg"', contents)

        client.run("export . lasote/testing")
        client.run("inspect MyPkg/1.2.3@lasote/testing -a=name")
        self.assertIn("name: MyPkg", client.out)
        client.run("inspect MyPkg/1.2.3@lasote/testing -a=version")
        self.assertIn("version: 1.2.3", client.out)

        client.run("upload MyPkg* --confirm")
        client.run('remove "*" -f')
        client.run("inspect MyPkg/1.2.3@lasote/testing -a=name -r=default")
        self.assertIn("name: MyPkg", client.out)
        client.run("inspect MyPkg/1.2.3@lasote/testing -a=version -r=default")
        self.assertIn("version: 1.2.3", client.out)

    def attributes_display_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "compiler", "arch"
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect . -a=short_paths")
        self.assertIn("short_paths: False", client.out)
        client.run("inspect . -a=name")
        self.assertIn("name: None", client.out)
        client.run("inspect . -a=version")
        self.assertIn("version: None", client.out)
        client.run("inspect . -a=settings")
        self.assertIn("settings: ('os', 'compiler', 'arch')", client.out)

        error = client.run("inspect . -a=unexisting_attr", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: 'Pkg' object has no attribute 'unexisting_attr'", client.out)

    def options_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"option1": [True, False], "option2": [1, 2, 3], "option3": "ANY",
               "option4": [1, 2]}
    default_options = "option1=False", "option2=2", "option3=randomANY"
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect . -a=options -a=default_options")
        self.assertEquals(client.out, """options
    option1: [True, False]
    option2: [1, 2, 3]
    option3: ANY
    option4: [1, 2]
default_options: ('option1=False', 'option2=2', 'option3=randomANY')
""")

        client.run("inspect . -a=version -a=name -a=options -a=default_options --json=file.json")
        contents = load(os.path.join(client.current_folder, "file.json"))
        json_contents = json.loads(contents)
        self.assertEqual(json_contents["version"], None)
        self.assertEqual(json_contents["name"], None)
        self.assertEqual(json_contents["options"], {'option4': [1, 2],
                                                    'option2': [1, 2, 3],
                                                    'option3': 'ANY',
                                                    'option1': [True, False]})
        self.assertEqual(json_contents["default_options"], ['option1=False',
                                                            'option2=2',
                                                            'option3=randomANY'])

    def inspect_all_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "MyPkg"
    version = "1.2.3"
    _private = "Nothing"
    def build(self):
        pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect .")
        self.assertIn("""name: MyPkg
version: 1.2.3
url: None
license: None
author: None
description: None
generators: ['txt']
exports: None
exports_sources: None
short_paths: False
apply_env: True
build_policy: None""", client.out)
