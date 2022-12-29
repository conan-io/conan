import os
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.util.env_reader import get_env
from conans.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID, GenConanfile


class CorruptedPackagesTest(unittest.TestCase):
    """
    Simulate a connection failure or file corruption in the server with missing files for a
    package and make sure the search, install are possible. Check re-upload is always possible
    even if the package in the server is not accessible
    """

    def setUp(self):
        revisions_enabled = get_env("TESTING_REVISIONS_ENABLED", False)
        self.server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
        self.client = TestClient(servers={"default": self.server})
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm -r default")
        # Check files are uploded in this order: conan_package.tgz, conaninfo.txt, conanmanifest.txt
        order1 = str(self.client.out).find("Uploading conan_package.tgz")
        order2 = str(self.client.out).find("Uploading conaninfo.txt", order1)
        order3 = str(self.client.out).find("Uploading conanmanifest.txt", order2)
        self.assertTrue(order1 < order2 < order3)
        rrev = "f3367e0e7d170aa12abccb175fee5f97" if revisions_enabled else "0"
        pref_str = "Pkg/0.1@user/testing#%s" % rrev
        prev = "83c38d3b4e5f1b8450434436eec31b00" if revisions_enabled else "0"
        self.pref = pref = PackageReference(ConanFileReference.loads(pref_str),
                                            NO_SETTINGS_PACKAGE_ID, prev)
        self.manifest_path = self.server.server_store.get_package_file_path(pref,
                                                                            "conanmanifest.txt")
        self.info_path = self.server.server_store.get_package_file_path(pref, "conaninfo.txt")
        self.tgz_path = self.server.server_store.get_package_file_path(pref, "conan_package.tgz")

    def _assert_all_package_files_in_server(self):
        self.assertTrue(os.path.exists(self.manifest_path))
        self.assertTrue(os.path.exists(self.info_path))
        self.assertTrue(os.path.exists(self.tgz_path))

    def test_info_manifest_missing(self):
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

    def test_manifest_missing(self):
        os.unlink(self.manifest_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        self.assertIn("Package_ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Binary package not found", self.client.out)
        self.assertIn(NO_SETTINGS_PACKAGE_ID, self.client.out)
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm")
        self._assert_all_package_files_in_server()

    def test_tgz_info_missing(self):
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
        self.assertIn("Uploading conan_package.tgz", self.client.out)
        self.assertIn("Uploading conaninfo.txt", self.client.out)
        self._assert_all_package_files_in_server()

    def test_tgz_missing(self):
        os.unlink(self.tgz_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Binary package not found", self.client.out)
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm")
        self.assertIn("Uploading conan_package.tgz", self.client.out)
        self._assert_all_package_files_in_server()

    def test_tgz_manifest_missing(self):
        os.unlink(self.tgz_path)
        os.unlink(self.manifest_path)
        # Try search
        self.client.run("search Pkg/0.1@user/testing -r default")
        self.assertIn("Package_ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)
        # Try fresh install
        self.client.run("remove * -f")
        self.client.run("install Pkg/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Binary package not found", self.client.out)
        # Try upload of fresh package
        self.client.run("create . Pkg/0.1@user/testing")
        self.client.run("upload * --all --confirm")
        self._assert_all_package_files_in_server()

    def test_tgz_manifest_info_missing(self):
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
