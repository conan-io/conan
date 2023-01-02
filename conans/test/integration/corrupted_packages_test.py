import os
import unittest

import pytest

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID, GenConanfile


class CorruptedPackagesTest(unittest.TestCase):
    """
    Simulate a connection failure or file corruption in the server with missing files for a
    package and make sure the search, install are possible. Check re-upload is always possible
    even if the package in the server is not accessible
    """

    def setUp(self):
        self.server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
        self.client = TestClient(servers={"default": self.server}, inputs=["admin", "password"])
        self.client.save({"conanfile.py": GenConanfile()})

        self.client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.client.run("upload * --confirm -r default")
        # Check files are uploded in this order: conan_package.tgz, conaninfo.txt, conanmanifest.txt
        order1 = str(self.client.out).find("Uploading conan_package.tgz")
        order2 = str(self.client.out).find("Uploading conaninfo.txt", order1)
        order3 = str(self.client.out).find("Uploading conanmanifest.txt", order2)
        self.assertTrue(order1 < order2 < order3)
        rrev = "4d670581ccb765839f2239cc8dff8fbd"
        pref_str = "pkg/0.1@user/testing#%s" % rrev
        prev = "cf924fbb5ed463b8bb960cf3a4ad4f3a"
        self.pref = pref = PkgReference(RecipeReference.loads(pref_str),
                                        NO_SETTINGS_PACKAGE_ID, prev)
        self.manifest_path = self.server.server_store.get_package_file_path(pref,
                                                                            "conanmanifest.txt")
        self.info_path = self.server.server_store.get_package_file_path(pref, "conaninfo.txt")
        self.tgz_path = self.server.server_store.get_package_file_path(pref, "conan_package.tgz")

    def _assert_all_package_files_in_server(self):
        self.assertTrue(os.path.exists(self.manifest_path))
        self.assertTrue(os.path.exists(self.info_path))
        self.assertTrue(os.path.exists(self.tgz_path))

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_info_manifest_missing(self):
        os.unlink(self.info_path)
        os.unlink(self.manifest_path)
        # Try search
        self.client.run("search pkg/0.1@user/testing -r default")
        self.assertIn("There are no packages for reference 'pkg/0.1@user/testing', "
                      "but package recipe found", self.client.out)
        # Try fresh install
        self.client.run("remove * -c")
        self.client.run("install --requires=pkg/0.1@user/testing", assert_error=True)
        self.assertIn(f"pkg/0.1@user/testing:{NO_SETTINGS_PACKAGE_ID} - Missing",
                      self.client.out)
        # Try upload of fresh package

        self.client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.client.run("upload * --confirm -r default")
        self._assert_all_package_files_in_server()

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_manifest_missing(self):
        os.unlink(self.manifest_path)
        # Try search
        self.client.run("search pkg/0.1@user/testing -r default")
        self.assertIn(f"Package_ID: {NO_SETTINGS_PACKAGE_ID}", self.client.out)
        # Try fresh install
        self.client.run("remove * -c")
        self.client.run("install --requires=pkg/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Binary package not found", self.client.out)
        self.assertIn(NO_SETTINGS_PACKAGE_ID, self.client.out)
        # Try upload of fresh package

        self.client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.client.run("upload * --confirm -r default")
        self._assert_all_package_files_in_server()

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_tgz_info_missing(self):
        os.unlink(self.tgz_path)
        os.unlink(self.info_path)
        # Try search
        self.client.run("search pkg/0.1@user/testing -r default")
        self.assertIn("There are no packages for reference 'pkg/0.1@user/testing', "
                      "but package recipe found", self.client.out)
        # Try fresh install
        self.client.run("remove * -c")
        self.client.run("install --requires=pkg/0.1@user/testing", assert_error=True)
        self.assertIn(f"pkg/0.1@user/testing:{NO_SETTINGS_PACKAGE_ID} - Missing", self.client.out)
        # Try upload of fresh package

        self.client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.client.run("upload * --confirm -r default")
        self.assertIn("Uploading conan_package.tgz", self.client.out)
        self.assertIn("Uploading conaninfo.txt", self.client.out)
        self._assert_all_package_files_in_server()

    @pytest.mark.xfail(reason="It is the server the one reporting errors or Not found")
    def test_tgz_missing(self):
        os.unlink(self.tgz_path)
        # Try search
        self.client.run("search pkg/0.1@user/testing -r default")
        # Try fresh install
        self.client.run("remove * -c")
        self.client.run("install --requires=pkg/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Binary package not found", self.client.out)
        # Try upload of fresh package
        self.client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        # We need the --force to actually fix a broken package
        # TODO: If the server reported missing package, or whatever, it wouldn't be necessary
        self.client.run("upload * --confirm -r default --force")
        self.assertIn("Uploading conan_package.tgz", self.client.out)
        self._assert_all_package_files_in_server()

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_tgz_manifest_missing(self):
        os.unlink(self.tgz_path)
        os.unlink(self.manifest_path)
        # Try search
        self.client.run("search pkg/0.1@user/testing -r default")
        self.assertIn(f"Package_ID: {NO_SETTINGS_PACKAGE_ID}", self.client.out)
        # Try fresh install
        self.client.run("remove * -c")
        self.client.run("install --requires=pkg/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Binary package not found", self.client.out)
        # Try upload of fresh package
        self.client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.client.run("upload * --confirm -r default")
        self._assert_all_package_files_in_server()

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_tgz_manifest_info_missing(self):
        os.unlink(self.tgz_path)
        os.unlink(self.manifest_path)
        os.unlink(self.info_path)
        # Try search
        self.client.run("search pkg/0.1@user/testing -r default")
        self.assertIn("There are no packages for reference 'pkg/0.1@user/testing', "
                      "but package recipe found", self.client.out)
        # Try fresh install
        self.client.run("remove * -c")
        self.client.run("install --requires=pkg/0.1@user/testing", assert_error=True)
        self.assertIn(f"pkg/0.1@user/testing:{NO_SETTINGS_PACKAGE_ID} - Missing", self.client.out)
        # Try upload of fresh package
        self.client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.client.run("upload * --confirm -r default")
        self._assert_all_package_files_in_server()
