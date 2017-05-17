import unittest
from conans.test.utils.tools import TestClient
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.paths import CONANFILE
from conans.util.files import mkdir, load
from conans.test.utils.test_files import temp_folder


class PackageCommandTest(unittest.TestCase):

    def package_errors_test(self):
        client = TestClient()
        client.run("package whatever@user/channel", ignore_error=True)
        self.assertIn("Wrong package recipe", client.user_io.out)

        client.run("package whatever/1.0@user/channel", ignore_error=True)
        self.assertIn("ERROR: Package recipe 'whatever/1.0@user/channel' does not exist",
                      client.user_io.out)

        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    name = "MyLib"
    version = "0.1"
"""
        client.save({CONANFILE: conanfile_template})
        client.run("export lasote/stable")
        client.run("package MyLib/0.1@lasote/stable", ignore_error=True)
        self.assertIn("ERROR: MyLib/0.1@lasote/stable: Package recipe has not been built locally",
                      client.user_io.out)

        builds_dir = client.paths.builds(ConanFileReference.loads("MyLib/0.1@lasote/stable"))
        os.makedirs(builds_dir)
        client.run("package MyLib/0.1@lasote/stable", ignore_error=True)
        self.assertIn("ERROR: MyLib/0.1@lasote/stable: Package recipe has not been built locally",
                      client.user_io.out)

        client.run("package MyLib/0.1@lasote/stable 1234", ignore_error=True)
        self.assertIn("ERROR: MyLib/0.1@lasote/stable: Package binary '1234' folder doesn't exist",
                      client.user_io.out)

    def local_package_test(self):
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
        client.run("install -g txt")
        client.run("build")
        origin_folder = client.current_folder
        client.current_folder = temp_folder()
        client.run('package "{0}" --build_folder="{0}"'.format(origin_folder))
        content = load(os.path.join(client.current_folder, "include/file.h"))
        self.assertEqual(content, "foo")

    def local_package_build_test(self):
        """Use 'conan package' to process locally the package method"""
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    exports = "*file.h"
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
"""
        files = {"include/file.h": "foo",
                 "include/file2.h": "bar",
                 CONANFILE: conanfile_template}

        client.save(files)
        origin_folder = client.current_folder
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run("install .. -g txt")
        # client.run("source ..")
        # self.assertEqual(os.listdir(os.path.join(client.current_folder, "include")), ["file.h"])
        # client.run("build ..")
        client.current_folder = temp_folder()
        client.run('package "{0}" --build_folder="{0}/build" --source_folder="{0}"'.format(origin_folder))
        content = load(os.path.join(client.current_folder, "include/file.h"))
        self.assertEqual(content, "foo")

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
        client.run("install -g env -g txt")
        client.run("source")
        client.run("build")
        client.run("package .", ignore_error=True)
        self.assertIn("ERROR: Cannot 'conan package' to the build folder", client.user_io.out)
        package_folder = os.path.join(origin_folder, "package")
        mkdir(package_folder)
        client.current_folder = package_folder
        client.run('package .. --build_folder=..')
        content = load(os.path.join(client.current_folder, "include/file.h"))
        self.assertEqual(content, "foo")

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
        files = {"lib/file1.a": "foo",
                 "include/file.h": "foo",
                 CONANFILE: conanfile_template}

        client.save(files)
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

        # Fix again conanfile and re-package with AL
        client.save({CONANFILE: conanfile_template.replace("self.copy", "pass #")})
        client.run("export lasote/stable")
        # Build and package conan file
        client.run("package %s" % str(conan_reference))
        self.assertIn("MyLib/0.1@lasote/stable: "
                      "Re-packaging 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", client.user_io.out)
        self.assertFalse(os.path.exists(os.path.join(package_path, "include", "file.h")))
        self.assertFalse(os.path.exists(os.path.join(package_path, "lib", "file1.a")))
