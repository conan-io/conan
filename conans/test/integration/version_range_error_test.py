import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE
from conans.test.utils.conanfile import TestConanFile


class VersionRangesErrorTest(unittest.TestCase):
    def verbose_version_test(self):
        client = TestClient()
        conanfile = TestConanFile("MyPkg", "0.1", requires=["MyOtherPkg/[~0.1]@user/testing"])
        client.save({CONANFILE: str(conanfile)})
        error = client.run("install . --build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("from requirement 'MyOtherPkg/[~0.1]@user/testing'", client.user_io.out)

    def werror_fail_test(self):
        client = TestClient()

        def add(name, version, requires=None):
            conanfile = TestConanFile(name, version, requires=requires)
            client.save({CONANFILE: str(conanfile)})
            client.run("export . user/testing")

        add("MyPkg1", "0.1.0")
        add("MyPkg1", "0.2.0")
        add("MyPkg2", "0.1", ["MyPkg1/[~0.1]@user/testing"])
        add("MyPkg3", "0.1", ["MyPkg1/[~0.2]@user/testing", "MyPkg2/[~0.1]@user/testing"])

        error = client.run("install . --build", ignore_error=True)
        self.assertTrue(error)
        self.assertNotIn("WARN: Version range '~0.1' required", client.out)
        self.assertIn("ERROR: Version range '~0.1' required by 'MyPkg2/0.1@user/testing' "
                      "not valid for downstream requirement 'MyPkg1/0.2.0@user/testing'",
                      client.out)
