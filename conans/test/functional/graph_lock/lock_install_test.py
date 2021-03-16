import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class LockInstallTest(unittest.TestCase):

    def test_install(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkga", "0.1").with_package_file("file.h", "0.1")})
        client.run("create . user/channel")

        # Use a consumer with a version range
        client.save({"conanfile.py":
                     GenConanfile("pkgb", "0.1").with_require("pkga/[>=0.1]@user/channel")})
        client.run("create . user/channel")
        client.run("lock create --reference=pkgb/0.1@user/channel --lockfile-out=lock1.lock")

        # We can create a pkga/0.2, but it will not be used
        client.save({"conanfile.py": GenConanfile("pkga", "0.2").with_package_file("file.h", "0.2")})
        client.run("create . user/channel")

        client.run("lock install lock1.lock -g deploy")
        self.assertIn("pkga/0.1@user/channel from local cache", client.out)
        file_h = client.load("pkga/file.h")
        self.assertEqual(file_h, "0.1")
