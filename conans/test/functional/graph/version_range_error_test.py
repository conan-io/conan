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
