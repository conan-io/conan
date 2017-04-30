import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE
from conans.test.utils.conanfile import TestConanFile


class VersionRangesErrorTest(unittest.TestCase):
    def verbose_version_test(self):
        client = TestClient()
        conanfile = TestConanFile("MyPkg", "0.1", requires=["MyOtherPkg/[~0.1]@user/testing"])
        client.save({CONANFILE: str(conanfile)})
        error = client.run("install --build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("from requirement 'MyOtherPkg/[~0.1]@user/testing'", client.user_io.out)
