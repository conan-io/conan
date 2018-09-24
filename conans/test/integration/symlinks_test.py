import os
import platform
import unittest

from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load, save, mkdir
from conans.model.ref import PackageReference, ConanFileReference

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
        os.symlink("latest", "edge")
        os.symlink("empty_folder", "broken_link")
        os.makedirs("other_empty_folder")
        os.symlink("other_empty_folder", "other_link")

    def package(self):
        self.copy("*.txt*", links=True)
        self.copy("*.so*", links=True)
"""

test_conanfile = """[requires]
Hello/0.1@lasote/stable

[imports]
., * -> .
"""


@unittest.skipUnless(platform.system() != "Windows", "Requires Symlinks")
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
            filepath = os.path.join(base, "edge/file2.txt")
            file1 = load(filepath)
            self.assertEqual("Hello2", file1)

    def basic_test(self):
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
        edge = os.path.join(client.current_folder, "edge")
        save(file1, "Hello1")
        os.symlink("file1.txt", file11)
        save(file2, "Hello2")
        os.symlink("version1", latest)
        os.symlink("latest", edge)
        client.run("export-pkg ./recipe Hello/0.1@lasote/stable")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        self._check(client, ref, build=False)

    def export_and_copy_test(self):
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

    def export_pattern_test(self):
        conanfile = """from conans import ConanFile
class ConanSymlink(ConanFile):
    name = "ConanSymlink"
    version = "3.0.0"
    exports_sources = %s
"""
        for export_sources in ["['src/*', 'CMakeLists.txt']", "['*', '!*another_directory*']"]:
            client = TestClient()
            client.save({"conanfile.py": conanfile % export_sources,
                         "src/main.cpp": "cpp fake content",
                         "CMakeLists.txt": "cmake fake content",
                         "another_directory/not_to_copy.txt": ""})
            mkdir(os.path.join(client.current_folder, "another_other_directory"))
            symlink_path = os.path.join(client.current_folder, "another_other_directory",
                                        "another_directory")
            symlinked_path = os.path.join(client.current_folder, "another_directory")
            self.assertFalse(os.path.exists(symlink_path))
            self.assertTrue(os.path.exists(symlinked_path))
            os.symlink(symlinked_path, symlink_path)
            client.run("export . danimtb/testing")
            ref = ConanFileReference("ConanSymlink", "3.0.0", "danimtb", "testing")
            export_sources = client.paths.export_sources(ref)
            cache_other_dir = os.path.join(export_sources, "another_other_directory")
            cache_src = os.path.join(export_sources, "src")
            cache_main = os.path.join(cache_src, "main.cpp")
            cache_cmake = os.path.join(export_sources, "CMakeLists.txt")
            self.assertFalse(os.path.exists(cache_other_dir))
            self.assertTrue(os.path.exists(cache_src))
            self.assertTrue(os.path.exists(cache_main))
            self.assertTrue(os.path.exists(cache_cmake))

    def export_ignore_case_test(self):
        conanfile = """from conans import ConanFile
class ConanSymlink(ConanFile):
    name = "ConanSymlink"
    version = "3.0.0"
    exports_sources = ["*"]
    def package(self):
        self.copy("*NOT_TO_COPY.TXT", ignore_case=%s)
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile % "False",
                     "src/main.cpp": "cpp fake content",
                     "CMakeLists.txt": "cmake fake content",
                     "another_directory/not_to_copy.txt": ""})
        mkdir(os.path.join(client.current_folder, "another_other_directory"))
        symlink_path = os.path.join(client.current_folder, "another_other_directory",
                                    "another_directory")
        symlinked_path = os.path.join(client.current_folder, "another_directory")
        self.assertFalse(os.path.exists(symlink_path))
        self.assertTrue(os.path.exists(symlinked_path))
        os.symlink(symlinked_path, symlink_path)
        client.run("create . danimtb/testing")
        ref = ConanFileReference("ConanSymlink", "3.0.0", "danimtb", "testing")
        cache_file = os.path.join(client.paths.export_sources(ref), "another_directory",
                                  "not_to_copy.txt")
        self.assertTrue(os.path.exists(cache_file))
        cache_other_dir = os.path.join(client.paths.export_sources(ref),
                                       "another_other_directory")
        self.assertTrue(os.path.exists(cache_other_dir))
        pkg_ref = PackageReference(ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_file = os.path.join(client.paths.package(pkg_ref), "another_directory",
                                    "not_to_copy.txt")
        self.assertFalse(os.path.exists(package_file))
        package_other_dir = os.path.join(client.paths.package(pkg_ref),
                                         "another_other_directory")
        self.assertFalse(os.path.exists(package_other_dir))
        client.save({"conanfile.py": conanfile % "True"})
        client.run("create . danimtb/testing")
        self.assertTrue(os.path.exists(package_file))
        self.assertTrue(os.path.exists(package_other_dir))
