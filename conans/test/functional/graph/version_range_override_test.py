# coding=utf-8

import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class VersionRangeOverrideTestCase(unittest.TestCase):

    def setUp(self):
        self.t = TestClient()
        self.t.save({"libB/conanfile.py": GenConanfile(),
                     "libC/conanfile.py":
                         GenConanfile().with_require_plain("libB/[<=2.0]@user/channel")})
        self.t.run("export libB libB/1.0@user/channel")
        self.t.run("export libB libB/2.0@user/channel")
        self.t.run("export libB libB/3.0@user/channel")
        self.t.run("export libC libC/1.0@user/channel")

        # Use the version range
        self.t.save({"conanfile.py": GenConanfile().with_require_plain("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libB/2.0@user/channel", self.t.out)

    def test_override_fix(self):
        # Override downstream with a fixed version
        self.t.save({"conanfile.py": GenConanfile().with_require_plain("libB/3.0@user/channel")
                                                   .with_require_plain("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libB/3.0@user/channel", self.t.out)

    def test_override_version_range(self):
        # Override downstream with a different version range
        self.t.save({"conanfile.py": GenConanfile().with_require_plain("libB/[>=2.x]@user/channel")
                                                   .with_require_plain("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libB/3.0@user/channel", self.t.out)
