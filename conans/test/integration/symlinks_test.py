import unittest
from conans.test.tools import TestClient
from conans.util.files import load
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

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        save("file1.txt", "Hello1")
        os.symlink("file1.txt", "file1.txt.1")

    def package(self):
        self.copy("*.txt*")
"""
        test_conanfile = """
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    requires = "Hello/0.1@lasote/stable"

    def imports(self):
        self.copy("*")

    def test(self):
        self.conanfile_directory
"""
        client.save({"conanfile.py": conanfile,
                     "test/conanfile.py": test_conanfile})
        client.run("test_package")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        file1 = load(os.path.join(client.paths.package(ref), "file1.txt"))
        print file1
