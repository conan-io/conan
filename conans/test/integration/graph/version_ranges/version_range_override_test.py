# coding=utf-8

import unittest

import pytest

from conans.test.utils.tools import TestClient, GenConanfile


@pytest.mark.xfail(reason="overrides have changed")
class VersionRangeOverrideTestCase(unittest.TestCase):

    def setUp(self):
        self.t = TestClient()
        self.t.save({"libb/conanfile.py": GenConanfile(),
                     "libC/conanfile.py":
                         GenConanfile().with_require("libb/[<=2.0]@user/channel")})
        self.t.run("export libB --name=libb --version=1.0 --user=user --channel=channel")
        self.t.run("export libB --name=libb --version=2.0 --user=user --channel=channel")
        self.t.run("export libB --name=libb --version=3.0 --user=user --channel=channel")
        self.t.run("export libC --name=libC --version=1.0 --user=user --channel=channel")

        # Use the version range
        self.t.save({"conanfile.py": GenConanfile().with_require("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libb/2.0@user/channel", self.t.out)

    def test_override_with_fixed_version(self):
        # Override upstream version range with a fixed version
        self.t.save({"conanfile.py": GenConanfile().with_require("libb/3.0@user/channel")
                                                   .with_require("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libb/3.0@user/channel", self.t.out)
        self.assertIn("WARN: libC/1.0@user/channel: requirement libb/[<=2.0]@user/channel overridden"
                      " by your conanfile to libb/3.0@user/channel", self.t.out)

    def test_override_using_version_range(self):
        # Override upstream version range with a different (narrower) version range
        self.t.save({"conanfile.py": GenConanfile().with_require("libb/[<2.x]@user/channel")
                                                   .with_require("libC/1.0@user/channel")})
        self.t.run("info . --only requires")
        self.assertIn("libb/1.0@user/channel", self.t.out)
        self.assertIn("WARN: libC/1.0@user/channel: requirement libb/[<=2.0]@user/channel overridden"
                      " by your conanfile to libb/1.0@user/channel", self.t.out)
        self.assertIn("Version range '<2.x' required by 'conanfile.py' resolved to"
                      " 'libb/1.0@user/channel' in local cache", self.t.out)
        self.assertIn("Version range '<=2.0' required by 'libC/1.0@user/channel' valid for"
                      " downstream requirement 'libb/1.0@user/channel'", self.t.out)

    def test_override_version_range_outside(self):
        # Override upstream version range with a different (non intersecting) version range
        self.t.save({"conanfile.py": GenConanfile().with_require("libb/[>2.x]@user/channel")
                                                   .with_require("libC/1.0@user/channel")})
        self.t.run("info . --only requires", assert_error=True)
        self.assertIn("WARN: libC/1.0@user/channel: requirement libb/[<=2.0]@user/channel overridden"
                      " by your conanfile to libb/3.0@user/channel", self.t.out)
        self.assertIn("ERROR: Version range '<=2.0' required by 'libC/1.0@user/channel' not valid"
                      " for downstream requirement 'libb/3.0@user/channel'", self.t.out)


class VersionRangeOverrideFailTestCase(unittest.TestCase):

    @pytest.mark.xfail(reason="overrides have changed")
    def test(self):
        # https://github.com/conan-io/conan/issues/7864
        t = TestClient()
        t.save({"conanfile.py": GenConanfile()})
        t.run("create . --name=gtest --version=1.8.0 --user=PORT --channel=stable")
        t.run("create . --name=gtest --version=1.8.1 --user=bloomberg --channel=stable")

        t.save({"conanfile.py": GenConanfile().with_require("gtest/1.8.0@PORT/stable")})
        t.run("create . --name=intermediate --version=1.0 --user=PORT --channel=stable")

        t.save({"conanfile.py": GenConanfile().with_requires("intermediate/1.0@PORT/stable")
               .with_tool_requires("gtest/1.8.0@PORT/stable")})
        t.run("create . --name=scubaclient --version=1.6 --user=PORT --channel=stable")

        # IMPORTANT: We need to override the private build-require in the profile too,
        # otherwise it will conflict, as it will not be overriden by regular requires
        t.save({"conanfile.py": GenConanfile().with_requires("gtest/1.8.1@bloomberg/stable",
                                                             "scubaclient/1.6@PORT/stable"),
                "myprofile": "[tool_requires]\ngtest/1.8.1@bloomberg/stable"})

        t.run("lock create conanfile.py --build -pr=myprofile")
        lock = t.load("conan.lock")
        self.assertIn("gtest/1.8.1@bloomberg/stable", lock)
        self.assertNotIn("gtest/1.8.0@PORT/stable", lock)

    def test_override(self):
        """
        pkga -> ros_perception  -> ros_core
           \\-----> pkgb  -----------/
        """
        # https://github.com/conan-io/conan/issues/8071
        t = TestClient()
        t.save({"conanfile.py": GenConanfile()})
        t.run("create . --name=ros_core --version=1.1.4 --user=3rdparty --channel=unstable")
        t.run("create . --name=ros_core --version=pr-53 --user=3rdparty --channel=snapshot")
        t.save({"conanfile.py": GenConanfile().with_requires("ros_core/1.1.4@3rdparty/unstable")})
        t.run("create . --name=ros_perception --version=1.1.4 --user=3rdparty --channel=unstable")
        t.run("create . --name=ros_perception --version=pr-53 --user=3rdparty --channel=snapshot")
        t.save({"conanfile.py": GenConanfile().with_requires("ros_core/[~1.1]@3rdparty/unstable")})
        t.run("create . --name=pkgb --version=0.1 --user=common --channel=unstable")
        t.save({"conanfile.py": GenConanfile("pkga", "0.1").with_requires(
            "ros_perception/[~1.1]@3rdparty/unstable",
            "pkgb/[~0]@common/unstable")})
        t.run("create . ")
        self.assertIn("ros_core/1.1.4@3rdparty/unstable", t.out)
        self.assertIn("ros_perception/1.1.4@3rdparty/unstable", t.out)
        self.assertNotIn("snapshot", t.out)

        t.save({"conanfile.py": GenConanfile("pkga", "0.1")
               .with_require("pkgb/[~0]@common/unstable")
               .with_require("ros_perception/pr-53@3rdparty/snapshot")
               .with_requirement("ros_core/pr-53@3rdparty/snapshot", override=True)})

        t.run("create .  --build=missing --build=pkga")
        self.assertIn("ros_core/pr-53@3rdparty/snapshot", t.out)
        self.assertIn("ros_perception/pr-53@3rdparty/snapshot", t.out)

        # Override only the upstream without overriding the direct one
        t.save({"conanfile.py": GenConanfile("pkga", "0.1")
               .with_require("pkgb/[~0]@common/unstable")
               .with_require("ros_perception/[~1.1]@3rdparty/unstable")
               .with_requirement("ros_core/pr-53@3rdparty/snapshot", force=True)})

        t.run("create .  --build=missing --build=pkga")
        self.assertIn("ros_core/pr-53@3rdparty/snapshot", t.out)
        self.assertIn("ros_perception/1.1.4@3rdparty/unstable", t.out)
