import unittest
from conans.test.tools import TestClient, TestServer
from conans.util.files import load, save
from conans.model.ref import PackageReference
import os
import platform

conanfile = """
from conans import ConanFile
from conans.util.files import save
import os

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        save("file1.txt", "Hello1")
        os.symlink("file1.txt", "file1.txt.1")

    def package(self):
        self.copy("*.txt*", links=True)
"""

test_conanfile = """[requires]
Hello/0.1@lasote/stable

[imports]
., * -> .
"""


class SymLinksTest(unittest.TestCase):

    def _check(self, client, ref, build=True):
        folders = [client.paths.package(ref), client.current_folder]
        if build:
            folders.append(client.paths.build(ref))
        for base in folders:
            filepath = os.path.join(base, "file1.txt")
            link = os.path.join(base, "file1.txt.1")
            self.assertEqual(os.readlink(link), "file1.txt")
            file1 = load(filepath)
            self.assertEqual("Hello1", file1)
            file1 = load(link)
            self.assertEqual("Hello1", file1)
            # Save any different string, random, or the base path
            save(filepath, base)
            self.assertEqual(load(link), base)

    def basic_test(self):
        if platform.system() == "Windows":
            return

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile})
        client.run("export lasote/stable")
        client.run("install --build -f=conanfile.txt")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        self._check(client, ref)

        client.run("install --build -f=conanfile.txt")
        self._check(client, ref)

    def upload_test(self):
        if platform.system() == "Windows":
            return

        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile})
        client.run("export lasote/stable")
        client.run("install --build -f=conanfile.txt")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        client.run("upload Hello/0.1@lasote/stable --all")
        client.run('remove "*" -f')
        client.save({"conanfile.txt": test_conanfile}, clean_first=True)
        client.run("install")
        self._check(client, ref, build=False)
