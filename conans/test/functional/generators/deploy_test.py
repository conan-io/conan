import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans import load
from conans.client.tools import chdir, replace_in_file
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class DeployGeneratorTest(unittest.TestCase):
    """
    Deploy generator set of tests with only one package
    """

    def setUp(self):
        conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Test(ConanFile):
            exports_sources = "*"

            def package(self):
                self.copy("*.h", dst="include")
                self.copy("*.lib", dst="my_libs")
                self.copy("*.config")
        """)

        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile,
                          "header.h": "",
                          "file.lib": "",
                          "file.config": ""})
        self.client.run("create . name/version@user/channel")
        self.client.current_folder = temp_folder()
        self.client.run("install name/version@user/channel -g deploy")

    def deploy_folder_path_test(self):
        base_path = os.path.join(self.client.current_folder, "name")
        expected_include_path = os.path.join(base_path, "include")
        expected_lib_path = os.path.join(base_path, "my_libs")
        self.assertTrue(os.path.exists(expected_include_path))
        self.assertTrue(os.path.exists(expected_lib_path))

    def deploy_manifest_path_test(self):
        expected_manifest_path = os.path.join(self.client.current_folder, "deploy_manifest.txt")
        self.assertTrue(os.path.exists(expected_manifest_path))

    def deploy_manifest_content_test(self):
        base_path = os.path.join(self.client.current_folder, "name")
        header_path = os.path.join(base_path, "include", "header.h")
        lib_path = os.path.join(base_path, "my_libs", "file.lib")
        config_path = os.path.join(base_path, "file.config")
        manifest_path = os.path.join(self.client.current_folder, "deploy_manifest.txt")
        content = load(manifest_path)
        self.assertIn(header_path, content)
        self.assertIn(lib_path, content)
        self.assertIn(config_path, content)

    def no_conan_metadata_files_test(self):
        metadata_files = ["conaninfo.txt", "conanmanifest.txt"]
        # Assert not in directory tree
        for root, _, _ in os.walk(self.client.current_folder):
            for name in metadata_files:
                self.assertNotIn(name, os.listdir(root))
        # Assert not in manifest
        manifest_path = os.path.join(self.client.current_folder, "deploy_manifest.txt")
        content = load(manifest_path)
        for name in metadata_files:
            self.assertNotIn(name, content)


class DeployGeneratorGraphTest(unittest.TestCase):
    """
    Deploy generator set of tests with more than one package in the graph
    """

    def setUp(self):
        conanfile1 = textwrap.dedent("""
        from conans import ConanFile

        class Test(ConanFile):
            exports_sources = "*"

            def package(self):
                self.copy("*.h", dst="include")
                self.copy("*.lib", dst="my_libs")
                self.copy("*.config")
        """)
        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile1,
                          "header1.h": "",
                          "file1.lib": "",
                          "file1.config": ""})
        self.client.run("create . name1/version@user/channel")

        conanfile2 = textwrap.dedent("""
        from conans import ConanFile

        class Test(ConanFile):
            exports_sources = "*"
            requires = "name1/version@user/channel"

            def package(self):
                self.copy("*.h", dst="include_files")
                self.copy("*.lib", dst="my_other_libs")
                self.copy("*.config", dst="build")
        """)
        self.client.save({"conanfile.py": conanfile2,
                          "header2.h": "",
                          "file2.lib": "",
                          "file2.config": ""}, clean_first=True)
        self.client.run("create . name2/version@user/channel")
        self.client.current_folder = temp_folder()
        self.client.run("install name2/version@user/channel -g deploy")

    def get_expected_paths(self):
        base1_path = os.path.join(self.client.current_folder, "name1")
        header1_path = os.path.join(base1_path, "include", "header1.h")
        lib1_path = os.path.join(base1_path, "my_libs", "file1.lib")
        config1_path = os.path.join(base1_path, "file1.config")

        base2_path = os.path.join(self.client.current_folder, "name2")
        header2_path = os.path.join(base2_path, "include_files", "header2.h")
        lib2_path = os.path.join(base2_path, "my_other_libs", "file2.lib")
        config2_path = os.path.join(base2_path, "build", "file2.config")

        return [header1_path, lib1_path, config1_path, header2_path, lib2_path, config2_path]

    def deploy_manifest_content_test(self):
        manifest_path = os.path.join(self.client.current_folder, "deploy_manifest.txt")
        content = load(manifest_path)
        for path in self.get_expected_paths():
            self.assertIn(path, content)

    def file_paths_test(self):
        for path in self.get_expected_paths():
            self.assertTrue(os.path.exists(path))
