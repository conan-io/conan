from conans.test.utils.tools import TestClient, TestServer
import unittest
from conans.util.files import load
import os


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
class Pkg(base.ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("inspect Base/0.1@lasote/testing -a=_my_var -r=default")
        self.assertIn("_my_var: 123", client.out)
        # Check that nothing was installed in the local cache, as the inspect put them in temps
        client.run("search")
        self.assertIn("There are no packages", client.out)

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
    options = {"option1": [True, False], "option2": [1, 2, 3], "option3": "ANY"}
    default_options = "option1=False", "option2=2", "option3=randomANY"
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect . -a=options")
        self.assertEquals(client.out, """options:
option1: ['False', 'True'], default=False
option2: ['1', '2', '3'], default=2
option3: ANY, default=randomANY
""")
