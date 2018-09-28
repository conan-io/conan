from conans.test.utils.tools import TestClient, TestServer
import unittest


class ConanInspectTest(unittest.TestCase):

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
        self.assertEquals(client.out, "name: MyPkg")
        client.run("inspect . -a=version")
        self.assertEquals(client.out, "version: 1.2.3")

        client.run("export . lasote/testing")
        client.run("inspect MyPkg/1.2.3@lasote/testing -a=name")
        self.assertEquals(client.out, "name: MyPkg")
        client.run("inspect MyPkg/1.2.3@lasote/testing -a=version")
        self.assertEquals(client.out, "version: 1.2.3")

        client.run("upload MyPkg* --confirm")
        client.run('remove "*" -f')
        client.run("inspect MyPkg/1.2.3@lasote/testing -a=name -r=default")
        self.assertEqual(client.out, "name: MyPkg")
        client.run("inspect MyPkg/1.2.3@lasote/testing -a=version -r=default")
        self.assertEquals(client.out, "version: 1.2.3")

    def attributes_display_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "compiler", "arch"
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect . -a=short_paths")
        self.assertEquals(client.out, "short_paths: False")
        client.run("inspect . -a=name")
        self.assertEquals(client.out, "name: None")
        client.run("inspect . -a=version")
        self.assertEquals(client.out, "version: None")
        client.run("inspect . -a=settings")
        self.assertEquals(client.out, "settings: ('os', 'compiler', 'arch')")

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
