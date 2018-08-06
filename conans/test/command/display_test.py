from conans.test.utils.tools import TestClient, TestServer
import unittest


class ConanDisplayTest(unittest.TestCase):

    def name_version_test(self):
        server = TestServer()
        client = TestClient(servers={"default": server}, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "MyPkg"
    version = "1.2.3"
"""
        client.save({"conanfile.py": conanfile})
        client.run("display . name")
        self.assertEquals(client.out, "MyPkg")
        client.run("display . version")
        self.assertEquals(client.out, "1.2.3")

        client.run("export . lasote/testing")
        client.run("display MyPkg/1.2.3@lasote/testing name")
        self.assertEquals(client.out, "MyPkg")
        client.run("display MyPkg/1.2.3@lasote/testing version")
        self.assertEquals(client.out, "1.2.3")

        client.run("upload MyPkg* --confirm")
        client.run('remove "*" -f')
        client.run("display MyPkg/1.2.3@lasote/testing name -r=default")
        self.assertEqual(client.out, "MyPkg")
        client.run("display MyPkg/1.2.3@lasote/testing version -r=default")
        self.assertEquals(client.out, "1.2.3")

    def attributes_display_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "compiler", "arch"
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("display . short_paths")
        self.assertEquals(client.out, "False")
        client.run("display . name")
        self.assertEquals(client.out, "None")
        client.run("display . version")
        self.assertEquals(client.out, "None")
        client.run("display . settings")
        self.assertEquals(client.out, "('os', 'compiler', 'arch')")

        error = client.run("display . unexisting_attr", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: type object 'Pkg' has no attribute 'unexisting_attr'", client.out)

    def options_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"option1": [True, False], "option2": [1, 2, 3], "option3": "ANY"}
    default_options = "option1=False", "option2=2", "option3=randomANY"
"""
        client.save({"conanfile.py": conanfile})
        client.run("display . options")
        self.assertEquals(client.out, """option1: ['False', 'True'], default=False
option2: ['1', '2', '3'], default=2
option3: ANY, default=randomANY""")

    def preexport_display_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile, load
import os
class Pkg(ConanFile):
    name = "MyPkg"
    @classmethod
    def preexport(self):
        self.version = load(os.path.join(self.recipe_folder, "version.txt"))
"""
        client.save({"conanfile.py": conanfile,
                     "version.txt": "1.2.3"})
        client.run("display . name")
        self.assertEqual("MyPkg", client.out)
        client.run("display . version")
        self.assertEqual("1.2.3", client.out)
