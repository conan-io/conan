import unittest
from conans.test.utils.tools import TestClient
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.paths import CONANFILE
from conans.util.files import mkdir, load
from conans.test.utils.test_files import temp_folder
from nose_parameterized import parameterized


class PackageCommandTest(unittest.TestCase):

    def bad_reference_error_test(self):
        client = TestClient()
        error = client.run("package whatever@user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Wrong package recipe reference", client.out)

    def unexisting_reference_error_test(self):
        client = TestClient()
        error = client.run("package whatever/1.0@user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package recipe 'whatever/1.0@user/channel' does not exist",
                      client.out)

    def package_errors_test(self):
        client = TestClient()

        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    name = "MyLib"
    version = "0.1"
"""
        client.save({CONANFILE: conanfile_template})
        client.run("export lasote/stable")
        error = client.run("package MyLib/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: MyLib/0.1@lasote/stable: Package has not been built in local cache",
                      client.out)

        error = client.run("package MyLib/0.1@lasote/stable 1234", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: MyLib/0.1@lasote/stable: Package binary '1234' folder doesn't exist",
                      client.out)

    def package_test(self):
        """Use 'conan package' command to repackage a generated package (without build it)"""
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    name = "MyLib"
    version = "0.1"
    exports = '*'

    def package(self):
        self.copy(pattern="*.h", dst="include", keep_path=False)
        #self.copy(pattern="*.a", dst="lib", keep_path=False)
"""

        client.save({"lib/file1.a": "foo",
                     "include/file.h": "foo",
                     CONANFILE: conanfile_template})
        client.run("export lasote/stable")

        # Build and package conan file
        conan_reference = ConanFileReference.loads("MyLib/0.1@lasote/stable")
        client.run("install %s --build missing" % str(conan_reference))
        package_id = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        package_path = client.paths.package(PackageReference(conan_reference, package_id))
        # Verify the headers are there but lib doesn't
        self.assertTrue(os.path.exists(os.path.join(package_path, "include", "file.h")))
        self.assertFalse(os.path.exists(os.path.join(package_path, "lib", "file1.a")))

        # Fix conanfile and re-package
        client.save({CONANFILE: conanfile_template.replace("#", "")})
        client.run("export lasote/stable")
        # Build and package conan file
        client.run("package %s %s" % (conan_reference, package_id))
        self.assertIn("MyLib/0.1@lasote/stable: "
                      "Re-packaging 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", client.user_io.out)
        self.assertTrue(os.path.exists(os.path.join(package_path, "include", "file.h")))
        self.assertTrue(os.path.exists(os.path.join(package_path, "lib", "file1.a")))

        # Fix again conanfile and re-package, repackaging ALL binaries
        client.save({CONANFILE: conanfile_template.replace("self.copy", "pass #")})
        client.run("export lasote/stable")
        # Build and package conan file
        client.run("package %s" % str(conan_reference))
        self.assertIn("MyLib/0.1@lasote/stable: "
                      "Re-packaging 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", client.user_io.out)
        self.assertFalse(os.path.exists(os.path.join(package_path, "include", "file.h")))
        self.assertFalse(os.path.exists(os.path.join(package_path, "lib", "file1.a")))


class PackageLocalCommandTest(unittest.TestCase):

    @parameterized.expand([(False, ), (True, )])
    def local_package_test(self, child_folder):
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
"""
        client.save({"include/file.h": "foo",
                     CONANFILE: conanfile_template})
        client.run("install")
        recipe_folder = client.current_folder
        if child_folder:
            package_folder = os.path.join(client.current_folder, "package")
            os.makedirs(package_folder)
        else:
            package_folder = temp_folder()
        client.current_folder = package_folder
        client.run('package "%s"' % recipe_folder)
        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(sorted(os.listdir(package_folder)),
                         sorted(["include", "conaninfo.txt", "conanmanifest.txt"]))
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])

    @parameterized.expand([(False, ), (True, )])
    def local_package_build_test(self, child_folder):
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
        self.copy(pattern="*.lib")
"""

        client.save({"include/file.h": "foo",
                     "build/lib/mypkg.lib": "mylib",
                     CONANFILE: conanfile_template})
        recipe_folder = client.current_folder
        client.current_folder = os.path.join(client.current_folder, "build")
        client.run("install ..")

        if child_folder:
            package_folder = os.path.join(recipe_folder, "package")
            os.makedirs(package_folder)
            client.current_folder = package_folder
            client.run('package .. --build_folder=../build')
        else:
            package_folder = temp_folder()
            client.current_folder = package_folder
            client.run('package "{0}" --build_folder="{0}/build"'.format(recipe_folder))
        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(sorted(os.listdir(package_folder)),
                         sorted(["include", "lib", "conaninfo.txt", "conanmanifest.txt"]))
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])
        self.assertEqual(os.listdir(os.path.join(package_folder, "lib")), ["mypkg.lib"])

    @parameterized.expand([(False, ), (True, )])
    def local_package_source_test(self, child_folder):
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
        self.copy(pattern="*.lib")
"""

        client.save({"src/include/file.h": "foo",
                     "build/lib/mypkg.lib": "mylib",
                     CONANFILE: conanfile_template})
        recipe_folder = client.current_folder
        client.current_folder = os.path.join(client.current_folder, "build")
        client.run("install ..")

        if child_folder:
            package_folder = os.path.join(recipe_folder, "package")
            os.makedirs(package_folder)
            client.current_folder = package_folder
            client.run('package .. --build_folder=../build --source_folder=../src')
        else:
            package_folder = temp_folder()
            client.current_folder = package_folder
            client.run('package "{0}" --build_folder="{0}/build" --source_folder="{0}/src"'.
                       format(recipe_folder))
        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(sorted(os.listdir(package_folder)),
                         sorted(["include", "lib", "conaninfo.txt", "conanmanifest.txt"]))
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])
        self.assertEqual(os.listdir(os.path.join(package_folder, "lib")), ["mypkg.lib"])

    def local_flow_test(self):
        """Use 'conan package' to process locally the package method"""
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
"""
        files = {"include/file.h": "foo",
                 CONANFILE: conanfile_template}

        client.save(files)
        origin_folder = client.current_folder
        client.run("install -g txt")
        client.run("source")
        client.run("build")
        error = client.run("package .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Cannot 'conan package' to the build folder", client.user_io.out)
        package_folder = os.path.join(origin_folder, "package")
        mkdir(package_folder)
        client.current_folder = package_folder
        client.run('package .. --build_folder=..')
        content = load(os.path.join(client.current_folder, "include/file.h"))
        self.assertEqual(content, "foo")
