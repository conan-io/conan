import unittest

from conans.paths import CONANFILE
from conans.test.utils.conanfile import TestConanFile
from conans.test.utils.tools import TestClient


class VersionRangesErrorTest(unittest.TestCase):
    def verbose_version_test(self):
        client = TestClient()
        conanfile = TestConanFile("MyPkg", "0.1", requires=["MyOtherPkg/[~0.1]@user/testing"])
        client.save({CONANFILE: str(conanfile)})
        client.run("install . --build", assert_error=True)
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

        client.run("install . --build", assert_error=True)
        self.assertNotIn("WARN: Version range '~0.1' required", client.out)
        self.assertIn("ERROR: Version range '~0.1' required by 'MyPkg2/0.1@user/testing' "
                      "not valid for downstream requirement 'MyPkg1/0.2.0@user/testing'",
                      client.out)
