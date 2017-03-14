import unittest
from conans.test.tools import TestClient
from conans.paths import CONANFILE


class VersionRangesConflictTest(unittest.TestCase):

    def setUp(self):
        conanfile = """
from conans import ConanFile
class MyConanA(ConanFile):
    name = "%s"
    version = "%s"
    %s
    """
        self.client = TestClient()

        def add(name, version, requires=None):
            requires = "requires=%s" % ",".join('"%s"' % r for r in requires) if requires else ""
            self.client.save({CONANFILE: conanfile % (name, version, requires)})
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
