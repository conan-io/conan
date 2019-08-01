import os
import platform
import stat
import unittest

from conans import load
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import GenConanfile, TurboTestClient, NO_SETTINGS_PACKAGE_ID


class DeployGeneratorTest(unittest.TestCase):
    """
    Deploy generator set of tests with only one package
    """

    def setUp(self):
        conanfile = GenConanfile()
        conanfile.with_package_file("include/header.h", "whatever")
        conanfile.with_package_file("my_libs/file.lib", "whatever")
        conanfile.with_package_file("file.config", "whatever")

        self.client = TurboTestClient()
        ref = ConanFileReference("name", "version", "user", "channel")
        self.client.create(ref, conanfile)
        self.client.current_folder = temp_folder()
        self.client.run("install %s -g deploy" % ref.full_str())

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
        conanfile1 = GenConanfile()
        conanfile1.with_package_file("include/header1.h", "whatever")
        conanfile1.with_package_file("my_libs/file1.lib", "whatever")
        conanfile1.with_package_file("file1.config", "whatever")
        ref1 = ConanFileReference("name1", "version", "user", "channel")

        conanfile2 = GenConanfile()
        conanfile2.with_requirement(ref1)
        conanfile2.with_package_file("include_files/header2.h", "whatever")
        conanfile2.with_package_file("my_other_libs/file2.lib", "whatever")
        conanfile2.with_package_file("build/file2.config", "whatever")
        ref2 = ConanFileReference("name2", "version", "user", "channel")

        self.client = TurboTestClient()
        self.client.create(ref1, conanfile1)
        self.client.create(ref2, conanfile2)
        self.client.current_folder = temp_folder()
        self.client.run("install %s -g deploy" % ref2.full_str())

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


class DeployGeneratorPermissionsTest(unittest.TestCase):
    """
    Test files deployed by the deploy generator are copied with same permissions
    """

    def setUp(self):
        conanfile1 = GenConanfile()
        conanfile1.with_package_file("include/header1.h", "whatever")
        self.ref1 = ConanFileReference("name1", "version", "user", "channel")

        self.client = TurboTestClient()
        self.client.create(self.ref1, conanfile1)
        layout = self.client.cache.package_layout(self.ref1)
        package_folder = layout.package(PackageReference(self.ref1, NO_SETTINGS_PACKAGE_ID))
        self.header_path = os.path.join(package_folder, "include", "header1.h")
        self.assertTrue(os.path.exists(self.header_path))

    @unittest.skipIf(platform.system() == "Windows", "Permissions in NIX systems only")
    def same_permissions_test(self):
        stat_info = os.stat(self.header_path)
        self.assertFalse(stat_info.st_mode & stat.S_IXUSR)
        os.chmod(self.header_path, stat_info.st_mode | stat.S_IXUSR)
        self.client.current_folder = temp_folder()
        self.client.run("install %s -g deploy" % self.ref1.full_str())
        base1_path = os.path.join(self.client.current_folder, "name1")
        header1_path = os.path.join(base1_path, "include", "header1.h")
        stat_info = os.stat(header1_path)
        self.assertTrue(stat_info.st_mode & stat.S_IXUSR)
