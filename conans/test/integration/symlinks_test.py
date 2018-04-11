import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load, save
from conans.model.ref import PackageReference, ConanFileReference
import os
import platform

conanfile = """
from conans import ConanFile
from conans.util.files import save
import os

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"

    def build(self):
        save("file1.txt", "Hello1")
        os.symlink("file1.txt", "file1.txt.1")
        save("version1/file2.txt", "Hello2")
        os.symlink("version1", "latest")

    def package(self):
        self.copy("*.txt*", links=True)
        self.copy("*.so*", links=True)
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
            filepath = os.path.join(base, "version1")
            link = os.path.join(base, "latest")
            self.assertEqual(os.readlink(link), "version1")
            filepath = os.path.join(base, "latest/file2.txt")
            file1 = load(filepath)
            self.assertEqual("Hello2", file1)

    def basic_test(self):
        if platform.system() == "Windows":
            return

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile})

        client.run("export . lasote/stable")
        client.run("install conanfile.txt --build")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        self._check(client, ref)

        client.run("install conanfile.txt --build")
        self._check(client, ref)

    def package_files_test(self):
        if platform.system() == "Windows":
            return

        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def package(self):
        self.copy("*", symlinks=True)
    """
        client.save({"recipe/conanfile.py": conanfile})
        file1 = os.path.join(client.current_folder, "file1.txt")
        file2 = os.path.join(client.current_folder, "version1/file2.txt")
        file11 = os.path.join(client.current_folder, "file1.txt.1")
        latest = os.path.join(client.current_folder, "latest")
        save(file1, "Hello1")
        os.symlink("file1.txt", file11)
        save(file2, "Hello2")
        os.symlink("version1", latest)
        client.run("export-pkg ./recipe Hello/0.1@lasote/stable")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        self._check(client, ref, build=False)

    def export_and_copy_test(self):
        if platform.system() == "Windows":
            return

        lib_name = "libtest.so.2"
        lib_contents = "TestLib"
        link_name = "libtest.so"

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile,
                     lib_name: lib_contents})

        pre_export_link = os.path.join(client.current_folder, link_name)
        os.symlink(lib_name, pre_export_link)

        client.run("export . lasote/stable")
        client.run("install conanfile.txt --build")
        client.run("copy Hello/0.1@lasote/stable team/testing --all")
        conan_ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        team_ref = ConanFileReference.loads("Hello/0.1@team/testing")
        package_ref = PackageReference(conan_ref,
                                       "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        team_package_ref = PackageReference(team_ref,
                                            "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        for folder in [client.paths.export(conan_ref), client.paths.source(conan_ref),
                       client.paths.build(package_ref), client.paths.package(package_ref),
                       client.paths.export(team_ref), client.paths.package(team_package_ref)]:
            exported_lib = os.path.join(folder, lib_name)
            exported_link = os.path.join(folder, link_name)
            self.assertEqual(os.readlink(exported_link), lib_name)

            self.assertEqual(load(exported_lib), load(exported_link))
            self.assertTrue(os.path.islink(exported_link))

        self._check(client, package_ref)

    def upload_test(self):
        if platform.system() == "Windows":
            return

        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile})

        client.run("export . lasote/stable")
        client.run("install conanfile.txt --build")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        client.run("upload Hello/0.1@lasote/stable --all")
        client.run('remove "*" -f')
        client.save({"conanfile.txt": test_conanfile}, clean_first=True)
        client.run("install conanfile.txt")
        self._check(client, ref, build=False)
