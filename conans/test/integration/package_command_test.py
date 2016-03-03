import unittest
from conans.test.tools import TestClient
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.paths import CONANFILE
from conans.util.files import save


class PackageCommandTest(unittest.TestCase):

    def package_test(self):
        """Use 'conan package' command to repackage a generated package (without build it)"""
        self.client = TestClient(users={"default":[("lasote", "mypass")]})
        conanfile_template = """
from conans import ConanFile, CMake
import platform

class MyConan(ConanFile):
    name = "MyLib"
    version = "0.1"
    generators = "cmake"
    exports = '*'

    def build(self):
        pass

    def package(self):
        self.copy(pattern="*.h", dst="include", keep_path=False)
#       self.copy(pattern="*.a", dst="lib", keep_path=False)


"""
        files = {"lib/file1.a": "foo",
                 "include/file.h": "foo",
                 CONANFILE: conanfile_template}

        self.client.save(files)
        self.client.run("export lasote/stable")

        # Build and package conan file
        conan_reference = ConanFileReference.loads("MyLib/0.1@lasote/stable")
        self.client.run("install %s --build missing" % str(conan_reference))

        package_id = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"

        package_path = self.client.paths.package(PackageReference(conan_reference, package_id))

        # Verify the headers are there but lib doesn't
        self.assertTrue(os.path.exists(os.path.join(package_path, "include", "file.h")))
        self.assertFalse(os.path.exists(os.path.join(package_path, "lib", "file1.a")))

        # Now we modify the package method and try again (NOTE: if build is called with raise)
        conanfile_template = """
from conans import ConanFile, CMake
import platform

class MyConan(ConanFile):
    name = "MyLib"
    version = "0.1"
    generators = "cmake"
    exports = '*'

    def build(self):
        raise Exception("DON'T WANT TO BUILD!")

    def package(self):
        self.copy(pattern="*.h", dst="include", keep_path=False)
        self.copy(pattern="*.a", dst="lib", keep_path=False)
"""

        files[CONANFILE] = conanfile_template

        self.client.save(files)
        self.client.run("export lasote/stable")

        # Build and package conan file
        self.client.run("package %s %s" % (conan_reference, package_id))

        # Verify the headers are there but lib doesn't
        self.assertTrue(os.path.exists(os.path.join(package_path, "include", "file.h")))
        self.assertTrue(os.path.exists(os.path.join(package_path, "lib", "file1.a")))

        # Now change a file by hand and regenerate manifest
        save(os.path.join(package_path, "newfile.txt"), "new content")
        self.client.run("package %s --all --only-manifest" % str(conan_reference))
        self.assertIn("Creating manifest for", self.client.user_io.out)
        self.client.run("install %s" % str(conan_reference))
        self.assertNotIn("Bad package", self.client.user_io.out)

        # And try to do the same without regenerate manifest
        save(os.path.join(package_path, "newfile2.txt"), "new content")
        self.client.run("install %s" % str(conan_reference), ignore_error=True)
        self.assertIn("Bad package", self.client.user_io.out)

        # Try to do it specifying the package (without --all)
        save(os.path.join(package_path, "newfile3.txt"), "new content")
        self.client.run("package %s %s --only-manifest" % (str(conan_reference), package_id))
        self.assertIn("Creating manifest for", self.client.user_io.out)
        self.client.run("install %s" % str(conan_reference))
        self.assertNotIn("Bad package", self.client.user_io.out)
