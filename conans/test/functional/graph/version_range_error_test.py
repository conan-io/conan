import unittest

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, GenConanfile


class VersionRangesErrorTest(unittest.TestCase):
    def verbose_version_test(self):
        client = TestClient()
        conanfile = GenConanfile().with_name("MyPkg").with_version("0.1")\
                                  .with_require_plain("MyOtherPkg/[~0.1]@user/testing")
        client.save({CONANFILE: str(conanfile)})
        client.run("install . --build", assert_error=True)
        self.assertIn("from requirement 'MyOtherPkg/[~0.1]@user/testing'", client.out)

    def werror_fail_test(self):
        client = TestClient()

        def add(name, version, requires=None):
            conanfile = GenConanfile().with_name(name).with_version(version)
            if requires:
                for req in requires:
                    ref = ConanFileReference.loads(req)
                    conanfile = conanfile.with_require(ref)
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
