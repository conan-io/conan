import os
import platform
import stat
import textwrap
import unittest

import pytest

from conans import load
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import save
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

    def test_deploy_folder_path(self):
        base_path = os.path.join(self.client.current_folder, "name")
        expected_include_path = os.path.join(base_path, "include")
        expected_lib_path = os.path.join(base_path, "my_libs")
        self.assertTrue(os.path.exists(expected_include_path))
        self.assertTrue(os.path.exists(expected_lib_path))

    def test_deploy_manifest_path(self):
        expected_manifest_path = os.path.join(self.client.current_folder, "deploy_manifest.txt")
        self.assertTrue(os.path.exists(expected_manifest_path))

    def test_deploy_manifest_content(self):
        base_path = os.path.join(self.client.current_folder, "name")
        header_path = os.path.join(base_path, "include", "header.h")
        lib_path = os.path.join(base_path, "my_libs", "file.lib")
        config_path = os.path.join(base_path, "file.config")
        manifest_path = os.path.join(self.client.current_folder, "deploy_manifest.txt")
        content = load(manifest_path)
        self.assertIn(header_path, content)
        self.assertIn(lib_path, content)
        self.assertIn(config_path, content)

    def test_no_conan_metadata_files(self):
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

    def test_deploy_manifest_content(self):
        manifest_path = os.path.join(self.client.current_folder, "deploy_manifest.txt")
        content = load(manifest_path)
        for path in self.get_expected_paths():
            self.assertIn(path, content)

    def test_file_paths(self):
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

    @pytest.mark.skipif(platform.system() == "Windows", reason="Permissions in NIX systems only")
    def test_same_permissions(self):
        stat_info = os.stat(self.header_path)
        self.assertFalse(stat_info.st_mode & stat.S_IXUSR)
        os.chmod(self.header_path, stat_info.st_mode | stat.S_IXUSR)
        self.client.current_folder = temp_folder()
        self.client.run("install %s -g deploy" % self.ref1.full_str())
        base1_path = os.path.join(self.client.current_folder, "name1")
        header1_path = os.path.join(base1_path, "include", "header1.h")
        stat_info = os.stat(header1_path)
        self.assertTrue(stat_info.st_mode & stat.S_IXUSR)


@pytest.mark.skipif(platform.system() == "Windows", reason="Permissions in NIX systems only")
class DeployGeneratorSymbolicLinkTest(unittest.TestCase):

    def setUp(self):
        conanfile = GenConanfile()
        conanfile.with_package_file("include/header.h", "whatever", link="include/header.h.lnk")
        self.ref = ConanFileReference("name", "version", "user", "channel")

        self.client = TurboTestClient()
        self.client.create(self.ref, conanfile)
        layout = self.client.cache.package_layout(self.ref)
        package_folder = layout.package(PackageReference(self.ref, NO_SETTINGS_PACKAGE_ID))
        self.header_path = os.path.join(package_folder, "include", "header.h")
        self.link_path = os.path.join(package_folder, "include", "header.h.lnk")

    def test_symbolic_links(self):
        self.client.current_folder = temp_folder()
        self.client.run("install %s -g deploy" % self.ref.full_str())
        base_path = os.path.join(self.client.current_folder, "name")
        header_path = os.path.join(base_path, "include", "header.h")
        link_path = os.path.join(base_path, "include", "header.h.lnk")
        self.assertTrue(os.path.islink(link_path))
        self.assertFalse(os.path.islink(header_path))
        linkto = os.path.join(os.path.dirname(link_path), os.readlink(link_path))
        self.assertEqual(linkto, header_path)

    def test_existing_link_symbolic_links(self):
        self.client.current_folder = temp_folder()
        base_path = os.path.join(self.client.current_folder, "name")
        header_path = os.path.join(base_path, "include", "header.h")
        link_path = os.path.join(base_path, "include", "header.h.lnk")
        save(link_path, "")
        self.client.run("install %s -g deploy" % self.ref.full_str())
        self.assertTrue(os.path.islink(link_path))
        self.assertFalse(os.path.islink(header_path))
        linkto = os.path.join(os.path.dirname(link_path), os.readlink(link_path))
        self.assertEqual(linkto, header_path)

    def test_existing_real_link_symbolic_links(self):
        self.client.current_folder = temp_folder()
        base_path = os.path.join(self.client.current_folder, "name")
        header_path = os.path.join(base_path, "include", "header.h")
        link_path = os.path.join(base_path, "include", "header.h.lnk")
        save(header_path, "")
        os.symlink(header_path, link_path)
        self.client.run("install %s -g deploy" % self.ref.full_str())
        self.assertTrue(os.path.islink(link_path))
        self.assertFalse(os.path.islink(header_path))
        linkto = os.path.join(os.path.dirname(link_path), os.readlink(link_path))
        self.assertEqual(linkto, header_path)

    def test_existing_broken_link_symbolic_links(self):
        self.client.current_folder = temp_folder()
        base_path = os.path.join(self.client.current_folder, "name")
        header_path = os.path.join(base_path, "include", "header.h")
        link_path = os.path.join(base_path, "include", "header.h.lnk")
        save(header_path, "")
        os.symlink(header_path, link_path)
        os.remove(header_path)  # This will make it a broken symlink
        self.client.run("install %s -g deploy" % self.ref.full_str())
        self.assertTrue(os.path.islink(link_path))
        self.assertFalse(os.path.islink(header_path))
        linkto = os.path.join(os.path.dirname(link_path), os.readlink(link_path))
        self.assertEqual(linkto, header_path)

    def test_existing_file_symbolic_links(self):
        self.client.current_folder = temp_folder()
        base_path = os.path.join(self.client.current_folder, "name")
        header_path = os.path.join(base_path, "include", "header.h")
        link_path = os.path.join(base_path, "include", "header.h.lnk")
        save(header_path, "")
        self.client.run("install %s -g deploy" % self.ref.full_str())
        self.assertTrue(os.path.islink(link_path))
        self.assertFalse(os.path.islink(header_path))
        linkto = os.path.join(os.path.dirname(link_path), os.readlink(link_path))
        self.assertEqual(linkto, header_path)


@pytest.mark.skipif(platform.system() == "Windows", reason="Symlinks in NIX systems only")
class DeployGeneratorSymbolicLinkFolderTest(unittest.TestCase):

    def setUp(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools

            class TestConan(ConanFile):

                def package(self):
                    folder_path = os.path.join(self.package_folder, "one_folder")
                    tools.mkdir(folder_path)
                    link_folder_path = os.path.join(self.package_folder, "other_folder")
                    with tools.chdir(os.path.dirname(folder_path)):
                        os.symlink(os.path.basename(folder_path), link_folder_path)
        """)
        self.ref = ConanFileReference("name", "version", "user", "channel")
        self.client = TurboTestClient()
        self.client.create(self.ref, conanfile)

    def test_symbolic_links(self):
        self.client.current_folder = temp_folder()
        self.client.run("install %s -g deploy" % self.ref.full_str())
        base_path = os.path.join(self.client.current_folder, "name")
        folder_path = os.path.join(base_path, "one_folder")
        link_folder_path = os.path.join(base_path, "other_folder")
        self.assertTrue(os.path.islink(link_folder_path))
        self.assertFalse(os.path.islink(folder_path))
        linkto_folder = os.path.join(os.path.dirname(link_folder_path),
                                     os.readlink(link_folder_path))
        self.assertEqual(linkto_folder, folder_path)
