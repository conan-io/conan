import os
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class LockInstallTest(unittest.TestCase):

    def test_install(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1").with_package_file("file.h", "0.1")})
        client.run("create . user/channel")

        # Use a consumer with a version range
        client.save({"conanfile.py":
                     GenConanfile("PkgB", "0.1").with_require("PkgA/[>=0.1]@user/channel")})
        client.run("create . user/channel")
        client.run("lock create --reference=PkgB/0.1@user/channel --lockfile-out=lock1.lock")

        client.save({"conanfile.py": GenConanfile("PkgA", "0.2").with_package_file("file.h", "0.2")})
        client.run("create . user/channel")

        client.run("lock install lock1.lock -g deploy")
        self.assertIn("PkgA/0.1@user/channel from local cache", client.out)
        file_h = client.load("PkgA/file.h")
        self.assertEqual(file_h, "0.1")
