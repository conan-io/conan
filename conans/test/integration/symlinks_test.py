import unittest
from conans.test.tools import TestClient
from conans.util.files import load, save
from conans.model.ref import PackageReference
import os
import platform


class SymLinksTest(unittest.TestCase):

    def basic_test(self):
        if platform.system() == "Windows":
            return

        client = TestClient()
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
        self.copy("*.txt*")
"""
        test_conanfile = """[requires]
Hello/0.1@lasote/stable

[imports]
., * -> .
"""
        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile})
        client.run("export lasote/stable")
        client.run("install . --build -f=conanfile.txt")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        for base in [client.paths.package(ref), client.paths.build(ref), client.current_folder]:
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
