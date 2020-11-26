import os
import platform
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, TestServer
from conans.client.tools.files import chdir
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID

conanfile = """
import os
from conans import ConanFile
class ExampleConan(ConanFile):
    name = "example"
    version = "0.1.0"
    exports_sources = "*"
    no_copy_source = True
    def package(self):
        {}
"""


@unittest.skipUnless(platform.system() != "Windows", "Requires Hardlinks")
class HardLinksTest(unittest.TestCase):

    FILE_SIZE = 1024 * 1024

    def validate_inodes(self, folder):
        inodes = []
        for filename in ["file_1MB", "file_1MB_link1", "file_1MB_link2"]:
            size = os.stat(os.path.join(folder, filename)).st_size
            pkg_inode = os.stat(os.path.join(folder, filename)).st_ino
            self.assertEqual(size, HardLinksTest.FILE_SIZE)
            inodes.append(pkg_inode)
        self.assertTrue(all(i == inodes[0] for i in inodes))

    def test_export_source_tgz_hardlink(self):
        """ Any hardlink MUST be preserved when packaged
        """
        client = TestClient(servers={"default": TestServer(write_permissions=[("*/*@*/*", "*")])},
                            users={"default": [("conan", "password")]})
        client.save({
            "conanfile.py": conanfile.replace("{}", 'self.copy("file*", src=self.source_folder)')})

        with chdir(client.current_folder):
            filename = "file_1MB"
            with open(filename, "wb") as fd:
                fd.write(os.urandom(HardLinksTest.FILE_SIZE))
            inode = os.stat(filename).st_ino
            for i in range(2):
                linkname = filename + "_link" + str(i + 1)
                os.link(filename, linkname)
                link_inode = os.stat(linkname).st_ino
                self.assertEqual(inode, link_inode)

        client.run("create . conan/testing")
        self.assertIn("package(): Packaged 3 files", client.out)

        # Each file must be 1MB
        ref = ConanFileReference("example", "0.1.0", "conan", "testing")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID, None)
        export_source_folder = client.cache.package_layout(pref.ref).export_sources()
        source_folder = client.cache.package_layout(pref.ref).source()
        package_folder = client.cache.package_layout(pref.ref).package(pref)
        download_folder = client.cache.package_layout(pref.ref).download_package(pref)
        self.validate_inodes(export_source_folder)
        self.validate_inodes(source_folder)
        self.validate_inodes(package_folder)

        inode_src = os.stat(os.path.join(source_folder, "file_1MB")).st_ino
        inode_exp = os.stat(os.path.join(export_source_folder, "file_1MB")).st_ino
        inode_pkg = os.stat(os.path.join(package_folder, "file_1MB")).st_ino
        self.assertNotEqual(inode_src, inode_exp)
        self.assertNotEqual(inode_src, inode_pkg)

        client.run("upload * --all --confirm")
        self.assertIn("Uploading conan_package.tgz", client.out)
        size = os.stat(os.path.join(download_folder, "conan_package.tgz")).st_size
        self.assertAlmostEqual(HardLinksTest.FILE_SIZE, size, delta=2000)

    def test_weak_point_export_hardlink(self):
        """ Exporting hardlinks only works when exporting all files at once
        """
        file_size = 1024 * 1024
        client = TestClient(servers={"default": TestServer(write_permissions=[("*/*@*/*", "*")])},
                            users={"default": [("conan", "password")]})

        client.save({
            "conanfile.py":
            conanfile.replace("{}",
        """self.copy("file_1MB", src=self.source_folder)
        self.copy("file_1MB_link1", src=self.source_folder)
        self.copy("file_1MB_link2", src=self.source_folder)
        """).replace("no_copy_source = True", "no_copy_source = False")})

        with chdir(client.current_folder):
            filename = "file_1MB"
            with open(filename, "wb") as fd:
                fd.write(os.urandom(file_size))
            inode = os.stat(filename).st_ino
            for i in range(2):
                linkname = filename + "_link" + str(i + 1)
                os.link(filename, linkname)
                link_inode = os.stat(linkname).st_ino
                self.assertEqual(inode, link_inode)

        client.run("create . conan/testing")
        self.assertIn("package(): Packaged 3 files", client.out)

        # Each file must be 1MB
        ref = ConanFileReference("example", "0.1.0", "conan", "testing")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID, None)
        export_source_folder = client.cache.package_layout(pref.ref).export_sources()
        source_folder = client.cache.package_layout(pref.ref).source()
        build_folder = client.cache.package_layout(pref.ref).build(pref)
        package_folder = client.cache.package_layout(pref.ref).package(pref)
        download_folder = client.cache.package_layout(pref.ref).download_package(pref)

        self.validate_inodes(export_source_folder)
        self.validate_inodes(source_folder)
        self.validate_inodes(build_folder)

        # package folder contains only copies
        i_1mb = os.stat(os.path.join(package_folder, "file_1MB")).st_ino
        i_1mb_lnk1 = os.stat(os.path.join(package_folder, "file_1MB_link1")).st_ino
        i_1mb_lnk2 = os.stat(os.path.join(package_folder, "file_1MB_link2")).st_ino
        self.assertNotEqual(i_1mb, i_1mb_lnk1)
        self.assertNotEqual(i_1mb, i_1mb_lnk2)
        self.assertNotEqual(i_1mb_lnk1, i_1mb_lnk2)

        client.run("upload * --all --confirm")
        self.assertIn("Uploading conan_package.tgz", client.out)
        size = os.stat(os.path.join(download_folder, "conan_package.tgz")).st_size
        self.assertAlmostEqual(3145728, size, delta=2000)
