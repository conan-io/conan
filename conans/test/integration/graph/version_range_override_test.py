# coding=utf-8

import unittest

from parameterized import parameterized

from conans.test.utils.tools import TestClient, GenConanfile


class VersionRangeOverrideTestCase(unittest.TestCase):

    def setUp(self):
        self.t = TestClient()
        self.t.save({"libB/conanfile.py": GenConanfile(),
                     "libC/conanfile.py":
                         GenConanfile().with_require("libB/[<=2.0]@user/channel")})
        self.t.run("export libB libB/1.0@user/channel")
        self.t.run("export libB libB/2.0@user/channel")
        self.t.run("export libB libB/3.0@user/channel")
        self.t.run("export libC libC/1.0@user/channel")

        # Use the version range
        self.t.save({"conanfile.py": GenConanfile().with_require("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libB/2.0@user/channel", self.t.out)

    def test_override_with_fixed_version(self):
        # Override upstream version range with a fixed version
        self.t.save({"conanfile.py": GenConanfile().with_require("libB/3.0@user/channel")
                                                   .with_require("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libB/3.0@user/channel", self.t.out)
        self.assertIn("WARN: libC/1.0@user/channel: requirement libB/[<=2.0]@user/channel overridden"
                      " by your conanfile to libB/3.0@user/channel", self.t.out)

    def test_override_using_version_range(self):
        # Override upstream version range with a different (narrower) version range
        self.t.save({"conanfile.py": GenConanfile().with_require("libB/[<2.x]@user/channel")
                                                   .with_require("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libB/1.0@user/channel", self.t.out)
        self.assertIn("WARN: libC/1.0@user/channel: requirement libB/[<=2.0]@user/channel overridden"
                      " by your conanfile to libB/1.0@user/channel", self.t.out)
        self.assertIn("Version range '<2.x' required by 'conanfile.py' resolved to"
                      " 'libB/1.0@user/channel' in local cache", self.t.out)
        self.assertIn("Version range '<=2.0' required by 'libC/1.0@user/channel' valid for"
                      " downstream requirement 'libB/1.0@user/channel'", self.t.out)

    def test_override_version_range_outside(self):
        # Override upstream version range with a different (non intersecting) version range
        self.t.save({"conanfile.py": GenConanfile().with_require("libB/[>2.x]@user/channel")
                                                   .with_require("libC/1.0@user/channel")})
        self.t.run("info . --only requires", assert_error=True)
        self.assertIn("WARN: libC/1.0@user/channel: requirement libB/[<=2.0]@user/channel overridden"
                      " by your conanfile to libB/3.0@user/channel", self.t.out)
        self.assertIn("ERROR: Version range '<=2.0' required by 'libC/1.0@user/channel' not valid"
                      " for downstream requirement 'libB/3.0@user/channel'", self.t.out)


class VersionRangeOverrideFailTestCase(unittest.TestCase):

    @parameterized.expand([(True,), (False,)])
    def test(self, host_context):
        # https://github.com/conan-io/conan/issues/7864
        t = TestClient()
        t.save({"conanfile.py": GenConanfile()})
        t.run("create . gtest/1.8.0@PORT/stable")
        t.run("create . gtest/1.8.1@bloomberg/stable")

        t.save({"conanfile.py": GenConanfile().with_require("gtest/1.8.0@PORT/stable")})
        t.run("create . intermediate/1.0@PORT/stable")

        if host_context:
            t.save({"conanfile.py": GenConanfile().with_requires("intermediate/1.0@PORT/stable")
                   .with_build_requirement("gtest/1.8.0@PORT/stable", force_host_context=True)})
        else:
            # WARNING: This test will fail in Conan 2.0, because build_requires will be by default
            # in the build-context and do not conflict
            t.save({"conanfile.py": GenConanfile().with_requires("intermediate/1.0@PORT/stable")
                   .with_build_requires("gtest/1.8.0@PORT/stable")})
        t.run("create . scubaclient/1.6@PORT/stable")

        # IMPORTANT: We need to override the private build-require in the profile too,
        # otherwise it will conflict, as it will not be overriden by regular requires
        t.save({"conanfile.py": GenConanfile().with_requires("gtest/1.8.1@bloomberg/stable",
                                                             "scubaclient/1.6@PORT/stable"),
                "myprofile": "[build_requires]\ngtest/1.8.1@bloomberg/stable"})

        t.run("lock create conanfile.py --build -pr=myprofile")
        lock = t.load("conan.lock")
        self.assertIn("gtest/1.8.1@bloomberg/stable", lock)
        self.assertNotIn("gtest/1.8.0@PORT/stable", lock)
