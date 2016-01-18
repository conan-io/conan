import unittest
from conans.test.tools import TestClient
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.paths import CONANFILE
import platform
import time
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from conans.test.utils.test_files import temp_folder


@attr("slow")
class MultiBuildTest(unittest.TestCase):

    def reuse_test(self):
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1")

        client = TestClient()
        client.save(files)
        client.run("export lasote/stable")

        configs = []  # ("gcc", "4.8")]
        # Place to add different compilers
        if platform.system() == "Windows2":
            configs.append(("Visual Studio", "12"))
        for compiler, compiler_version in configs:
            client.default_settings(compiler, compiler_version)
            client.run("install %s --build missing" % str(conan_reference))

        # Check compilation ok
        package_ids = client.paths.conan_packages(conan_reference)
        self.assertEquals(len(package_ids), len(configs))
        for package_id in package_ids:
            package_ref = PackageReference(conan_reference, package_id)
            self._assert_library_exists(package_ref, client.paths)

        # Reuse them
        conan_reference = ConanFileReference.loads("Hello1/0.2@lasote/stable")
        files3 = cpp_hello_conan_files("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        client.current_folder = temp_folder()

        client.save(files3)
        for compiler, compiler_version in configs:
            client.default_settings(compiler, compiler_version)
            client.run('install')
            client.run('build')

            command = os.sep.join([".", "bin", "say_hello"])
            client.runner(command, cwd=client.current_folder)
            self.assertIn("Hello Hello1", client.user_io.out)
            self.assertIn("Hello Hello0", client.user_io.out)

        new_conanfile = files3[CONANFILE].replace('"language": 0', '"language": 1')
        for compiler, compiler_version in configs:
            client.default_settings(compiler, compiler_version)
            client.save({CONANFILE: new_conanfile})
            client.run('install')
            client.run('build')
            time.sleep(1)

            client.runner(command, cwd=client.current_folder)
            self.assertIn("Hola Hello1", client.user_io.out)
            self.assertIn("Hola Hello0", client.user_io.out)

    def _assert_library_exists(self, package_ref, paths):
        package_path = paths.package(package_ref)
        self.assertTrue(os.path.exists(os.path.join(package_path, "lib")))
        libraries = os.listdir(os.path.join(package_path, "lib"))
        self.assertEquals(len(libraries), 1)
        self.assertTrue(os.path.basename(libraries[0]).startswith("libhello"))
