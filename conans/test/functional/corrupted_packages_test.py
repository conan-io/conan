import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID


class CorruptedPackagesTest(unittest.TestCase):
    """
    Simulate a connection failure or file corruption in the server with missing files for a
    package and make sure the search, install are possible. Check re-upload is always possible
    even if the package in the server is not accessible
    """

    def setUp(self):
        self.server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
        self.client = TestClient(servers={"default": self.server})
        conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):
            pass
        """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm -r default")
        self.pref = pref = PackageReference(ConanFileReference.loads("Pkg/0.1@user/testing#0"),
                                NO_SETTINGS_PACKAGE_ID, "0")
        self.manifest_path = self.server.server_store.get_package_file_path(pref,
                                                                            "conanmanifest.txt")
        self.info_path = self.server.server_store.get_package_file_path(pref, "conaninfo.txt")
        self.tgz_path = self.server.server_store.get_package_file_path(pref, "conan_package.tgz")

    def _assert_all_package_files_in_server(self):
        self.assertTrue(os.path.exists(self.manifest_path))
        self.assertTrue(os.path.exists(self.info_path))
        self.assertTrue(os.path.exists(self.tgz_path))

    def info_manifest_missing_test(self):
        os.unlink(self.info_path)
        os.unlink(self.manifest_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        self.assertIn("There are no packages for reference 'Pkg/0.1@user/testing', "
                      "but package recipe found", self.client.out)
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Pkg/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Missing",
                      self.client.out)
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm -r default")
        self._assert_all_package_files_in_server()

    def manifest_missing_test(self):
        os.unlink(self.manifest_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        self.assertIn("Package_ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing")  # FIXME: missing conanmanifest.txt does NOT fail?
        self.assertIn(NO_SETTINGS_PACKAGE_ID, self.client.out)
        # Try upload of installed package
        self.client.run("upload * --all --confirm", assert_error=True)
        self.assertIn("ERROR: Cannot upload corrupted package", self.client.out)
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm")
        self._assert_all_package_files_in_server()

    def tgz_info_missing_test(self):
        os.unlink(self.tgz_path)
        os.unlink(self.info_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        self.assertIn("There are no packages for reference 'Pkg/0.1@user/testing', "
                      "but package recipe found", self.client.out)
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Pkg/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Missing",
                      self.client.out)
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm")
        # FIXME: tgz and info are not in the server and not uploaded
        self.assertIn("Package is up to date, upload skipped", self.client.user_io.out)
        # self._assert_all_package_files_in_server()

    def tgz_missing_test(self):
        os.unlink(self.tgz_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing")
        print(self.client.out)  # FIXME: missing conan_package.tgz does NOT fail?
        self.assertIn(NO_SETTINGS_PACKAGE_ID, self.client.out)
        self.client.run("upload * --all --confirm")
        print(self.client.out)  # FIXME: Package up to date but actually the tgz is missing in the server
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm")
        # FIXME: tgz is not in the server and not uploaded
        self.assertIn("Package is up to date, upload skipped", self.client.user_io.out)
        #self._assert_all_package_files_in_server()

    def tgz_manifest_missing_test(self):
        os.unlink(self.tgz_path)
        os.unlink(self.manifest_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        self.assertIn("Package_ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing")  # FIXME: missing conan_package.tgz and conanmanifest.txt does NOT fail?
        # Try upload of installed package
        self.client.run("upload * --all --confirm", assert_error=True)
        self.assertIn("ERROR: Cannot upload corrupted package", self.client.out)
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm")
        self._assert_all_package_files_in_server()

    def tgz_manifest_info_missing_test(self):
        os.unlink(self.tgz_path)
        os.unlink(self.manifest_path)
        os.unlink(self.info_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        self.assertIn("There are no packages for reference 'Pkg/0.1@user/testing', "
                      "but package recipe found", self.client.out)
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing", assert_error=True)
        self.assertIn("Pkg/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Missing",
                      self.client.out)
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm")
        self._assert_all_package_files_in_server()
