import unittest

from conans import tools
from conans.test.utils.tools import TestClient
import os
from conans.paths import CONANFILE
from conans.util.files import load, mkdir
from conans.test.utils.test_files import temp_folder
from parameterized import parameterized


class PackageLocalCommandTest(unittest.TestCase):

    def package_with_destination_test(self):
        client = TestClient()

        def prepare_for_package(the_client):
            the_client.save({"src/header.h": "contents"}, clean_first=True)
            the_client.run("new lib/1.0 -s")

            # don't need build method
            tools.replace_in_file(os.path.join(client.current_folder, "conanfile.py"),
                                  "def build",
                                  "def skip_build")
            the_client.run("install . --install-folder build")
            mkdir(os.path.join(client.current_folder, "build2"))

        # In current dir subdir
        prepare_for_package(client)
        client.run("package . --build-folder build2 --install-folder build --package-folder=subdir")
        self.assertNotIn("package(): WARN: No files copied", client.out)
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "subdir")))

        # In current dir subdir with conanfile path
        prepare_for_package(client)
        client.run("package ./conanfile.py --build-folder build2 --install-folder build --package-folder=subdir")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "subdir")))

        # Default path
        prepare_for_package(client)
        client.run("package . --build-folder build")
        self.assertNotIn("package(): WARN: No files copied", client.out)
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build", "package")))

        # Default path with conanfile path
        prepare_for_package(client)
        client.run("package conanfile.py --build-folder build")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build", "package")))

        # Abs path
        prepare_for_package(client)
        pf = os.path.join(client.current_folder, "mypackage/two")
        client.run("package . --build-folder build --package-folder='%s'" % pf)
        self.assertNotIn("package(): WARN: No files copied", client.out)
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "mypackage", "two")))

        # Abs path with conanfile path
        prepare_for_package(client)
        pf = os.path.join(client.current_folder, "mypackage/two")
        os.rename(os.path.join(client.current_folder, "conanfile.py"),
                  os.path.join(client.current_folder, "my_conanfile.py"))
        client.run("package ./my_conanfile.py --build-folder build --package-folder='%s'" % pf)
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "mypackage", "two")))

    def package_with_path_errors_test(self):
        client = TestClient()
        client.save({"conanfile.txt": "contents"}, clean_first=True)

        # Path with conanfile.txt
        error = client.run("package conanfile.txt --build-folder build2 --install-folder build",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("A conanfile.py is needed (not valid conanfile.txt)", client.out)

        # Path with wrong conanfile path
        error = client.run("package not_real_dir/conanfile.py --build-folder build2 --install-folder build",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Conanfile not found: %s" % os.path.join(client.current_folder, "not_real_dir",
                                                               "conanfile.py"), client.out)

    def package_with_reference_errors_test(self):
        client = TestClient()
        error = client.run("package MyLib/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conan package' doesn't accept a reference anymore",
                      client.out)

    def local_package_test(self):
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
"""
        client.save({"include/file.h": "foo",
                     CONANFILE: conanfile_template})
        client.run("install .")
        path = client.current_folder
        client.run('package "%s"' % path)
        package_folder = os.path.join(client.current_folder, "package")
        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(sorted(os.listdir(package_folder)),
                         sorted(["include", "conaninfo.txt", "conanmanifest.txt"]))
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])

    @parameterized.expand([(False, False), (True, False), (True, True), (False, True)])
    def local_package_build_test(self, default_folder, conanfile_path):
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
        path = client.current_folder
        client.current_folder = os.path.join(client.current_folder, "build")
        client.run("install ..")

        if default_folder:
            package_folder = os.path.join(client.current_folder, "package")
            path = "../conanfile.py" if conanfile_path else ".."
            client.run('package {0} --build-folder=.'.format(path))
            self.assertEqual(sorted(os.listdir(package_folder)),
                             sorted(["include", "lib", "conaninfo.txt", "conanmanifest.txt"]))
        else:
            package_folder = temp_folder()
            client.current_folder = package_folder
            build_folder = os.path.join(path, "build")

            if conanfile_path:
                path = os.path.join(path, "conanfile.py")

            client.run('package "{0}" --build-folder="{2}"'
                       ' --package-folder="{1}"'.format(path, package_folder, build_folder))
            self.assertEqual(sorted(os.listdir(package_folder)),
                             sorted(["include", "lib", "conaninfo.txt",
                                     "conanmanifest.txt"]))

        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])
        self.assertEqual(os.listdir(os.path.join(package_folder, "lib")), ["mypkg.lib"])

    @parameterized.expand([(False, False), (True, False), (True, True), (False, True)])
    def local_package_source_test(self, default_folder, conanfile_path):
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
        self.copy(pattern="*.lib")
        self.copy(pattern="myapp", src="bin", dst="bin")
"""

        client.save({"src/include/file.h": "foo",
                     "build/lib/mypkg.lib": "mylib",
                     "build/bin/myapp": "",
                     CONANFILE: conanfile_template})
        conanfile_folder = client.current_folder
        path = conanfile_folder
        client.current_folder = os.path.join(client.current_folder, "build")
        client.run("install ..")

        if default_folder:
            package_folder = os.path.join(client.current_folder, "package")
            path = "../conanfile.py" if conanfile_path else ".."
            client.run('package {0} --build-folder=. --source-folder=../src'.format(path))
        else:
            package_folder = temp_folder()

            if conanfile_path:
                path = os.path.join(path, "conanfile.py")

            client.run('package "{0}" --build-folder="{1}/build" '
                       '--package-folder="{2}" --source-folder="{1}/src"'.
                       format(path, conanfile_folder, package_folder))
        self.assertNotIn("package(): Copied 1 \'\' file", client.out)
        self.assertIn("package(): Copied 1 file: myapp", client.out)
        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(sorted(os.listdir(package_folder)),
                         sorted(["include", "lib", "bin", "conaninfo.txt", "conanmanifest.txt"]))
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])
        self.assertEqual(os.listdir(os.path.join(package_folder, "lib")), ["mypkg.lib"])
        self.assertEqual(os.listdir(os.path.join(package_folder, "bin")), ["myapp"])

    def no_files_copied_local_package_test(self):
        # https://github.com/conan-io/conan/issues/2753
        client = TestClient()
        conanfile = """
from conans import ConanFile

class MyConan(ConanFile):
    def build(self):
        pass
    def package(self):
        self.copy(pattern="*.lib")
"""
        client.save({"source/include/file.h": "foo",
                     "build/bin/library.lib": "",
                     CONANFILE: conanfile})
        client.run("install . --install-folder=install")
        client.run('package . --source-folder=source --install-folder=install --build-folder=build')
        self.assertIn("No files copied from source folder!", client.out)
        self.assertIn("Copied 1 '.lib' file: library.lib", client.out)

        conanfile = """
from conans import ConanFile

class MyConan(ConanFile):
    def build(self):
        pass
    def package(self):
        self.copy(pattern="*.h")
"""
        client.save({CONANFILE: conanfile})
        client.run('package . --source-folder=source --install-folder=install --build-folder=build')
        self.assertIn("No files copied from build folder!", client.out)
        self.assertIn("Copied 1 '.h' file: file.h", client.out)

        conanfile = """
from conans import ConanFile

class MyConan(ConanFile):
    def build(self):
        pass
    def package(self):
        self.copy(pattern="*.fake")
"""
        client.save({CONANFILE: conanfile})
        client.run('package . --source-folder=source --install-folder=install --build-folder=build')
        self.assertIn("No files copied from source folder!", client.out)
        self.assertIn("No files copied from build folder!", client.out)
        self.assertNotIn("Copied 1 '.h' file: file.h", client.out)
        self.assertNotIn("Copied 1 '.lib' file: library.lib", client.out)
