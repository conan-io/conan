import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE
from conans.test.utils.conanfile import TestConanFile


class VersionRangesConflictTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

        def add(name, version, requires=None):
            conanfile = TestConanFile(name, version, requires=requires)
            self.client.save({CONANFILE: str(conanfile)})
            self.client.run("export user/testing")
        add("MyPkg1", "0.1.0")
        add("MyPkg1", "0.2.0")
        add("MyPkg2", "0.1", ["MyPkg1/[~0.1]@user/testing"])
        add("MyPkg3", "0.1", ["MyPkg1/[~0.2]@user/testing", "MyPkg2/[~0.1]@user/testing"])

    def werror_warn_test(self):
        self.client.run("info")
        self.assertIn("WARN: Version range '~0.1' required by 'MyPkg2/0.1@user/testing' "
                      "not valid for downstream requirement 'MyPkg1/0.2.0@user/testing'",
                      self.client.user_io.out)

    def werror_fail_test(self):
        error = self.client.run("install --build --werror", ignore_error=True)
        self.assertTrue(error)
        self.assertNotIn("WARN: Version range '~0.1' required", self.client.user_io.out)
        self.assertIn("ERROR: Version range '~0.1' required by 'MyPkg2/0.1@user/testing' "
                      "not valid for downstream requirement 'MyPkg1/0.2.0@user/testing'",
                      self.client.user_io.out)
