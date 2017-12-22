import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import save
import os
from conans.model.ref import ConanFileReference, PackageReference


class ReadOnlyTest(unittest.TestCase):

    def setUp(self):
        self.test_server = TestServer()
        client = TestClient(servers={"default": self.test_server},
                            users={"default": [("lasote", "mypass")]})
        client.run("--version")
        client.run("config set general.read_only_cache=True")
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    exports_sources = "*.h"
    def package(self):
        self.copy("*")
"""
        client.save({"conanfile.py": conanfile,
                     "myheader.h": "my header"})
        client.run("create . Pkg/0.1@lasote/channel")
        self.client = client

    def basic_test(self):
        ref = PackageReference(ConanFileReference.loads("Pkg/0.1@lasote/channel"),
                               "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        path = os.path.join(self.client.client_cache.package(ref), "myheader.h")
        with self.assertRaises(IOError):
            save(path, "Bye World")
        os.chmod(path, 0o777)
        save(path, "Bye World")

    def remove_test(self):
        self.client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", self.client.out)
        self.client.run("remove Pkg* -f")
        self.assertNotIn("Pkg/0.1@lasote/channel", self.client.out)

    def upload_test(self):
        self.client.run("upload * --all --confirm")
        self.client.run("remove Pkg* -f")
        self.client.run("install Pkg/0.1@lasote/channel")
        self.basic_test()

    def upload_change_test(self):
        self.client.run("upload * --all --confirm")
        client = TestClient(servers={"default": self.test_server},
                            users={"default": [("lasote", "mypass")]})
        client.run("install Pkg/0.1@lasote/channel")
        ref = PackageReference(ConanFileReference.loads("Pkg/0.1@lasote/channel"),
                               "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        path = os.path.join(client.client_cache.package(ref), "myheader.h")
        with self.assertRaises(IOError):
            save(path, "Bye World")
        os.chmod(path, 0o777)
        save(path, "Bye World")
