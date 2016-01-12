import unittest
from conans.test.tools import TestClient, TestServer
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import rmdir


class CopyPackagesTest(unittest.TestCase):

    def test_copy_command(self):
        test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                 [],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers,  users=[("lasote", "mypass")])
        self._export_some_packages(self.client)
        self.ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        # Copy all packages
        new_reference = ConanFileReference.loads("Hello0/0.1@pepe/testing")
        self.client.run("copy Hello0/0.1@lasote/stable pepe/testing --all --force")
        p1 = self.client.paths.packages(new_reference)
        packages = os.listdir(p1)
        self.assertEquals(len(packages), 3)

        # Copy just one
        rmdir(p1)
        self.client.run("copy Hello0/0.1@lasote/stable pepe/testing -p %s --force" % packages[0])
        packages = os.listdir(p1)
        self.assertEquals(len(packages), 1)

    def _export_some_packages(self, client):
        files = cpp_hello_conan_files("Hello0", "0.1")
        # No build.
        files[CONANFILE] = files[CONANFILE].replace("def build(self):", "def build(self):\n        return\n")
        client.save(files)
        client.run("export lasote/stable")
        client.run("install Hello0/0.1@lasote/stable -s os=Windows --build missing")
        client.run("install Hello0/0.1@lasote/stable -s os=Linux --build missing")
        client.run("install Hello0/0.1@lasote/stable -s os=Linux -s compiler=gcc -s compiler.version=4.6  --build missing")
