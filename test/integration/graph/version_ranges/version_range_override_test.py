import json

import pytest

from conan.test.utils.tools import TestClient, GenConanfile


class TestVersionRangeOverride:

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.t = TestClient(light=True)
        self.t.save({"libb/conanfile.py": GenConanfile(),
                     "libc/conanfile.py":
                         GenConanfile().with_require("libb/[<=2.0]@user/channel")})
        self.t.run("export libb --name=libb --version=1.0 --user=user --channel=channel")
        self.t.run("export libb --name=libb --version=2.0 --user=user --channel=channel")
        self.t.run("export libb --name=libb --version=3.0 --user=user --channel=channel")
        self.t.run("export libc --name=libc --version=1.0 --user=user --channel=channel")

    def test(self):
        # Use the version range
        self.t.save({"conanfile.py": GenConanfile().with_require("libc/1.0@user/channel")})
        self.t.run("graph info . --filter requires")
        assert "libb/2.0@user/channel" in self.t.out

    def test_override_with_fixed_version(self):
        # Override upstream version range with a fixed version
        self.t.save({"conanfile.py": GenConanfile().with_requirement("libb/3.0@user/channel",
                                                                     override=True)
                                                   .with_require("libc/1.0@user/channel")})
        self.t.run("graph info . --filter requires")
        self.t.assert_overrides({'libb/[<=2.0]@user/channel': ['libb/3.0@user/channel']})
        assert "libb/3.0@user/channel#" in self.t.out

    def test_override_using_version_range(self):
        # Override upstream version range with a different (narrower) version range
        self.t.save({"conanfile.py": GenConanfile().with_requirement("libb/[<2.x]@user/channel",
                                                                     override=True)
                                                   .with_require("libc/1.0@user/channel")})
        self.t.run("graph info . --filter requires")
        self.t.assert_overrides({'libb/[<=2.0]@user/channel': ['libb/[<2.x]@user/channel']})
        assert "libb/2.0@user/channel" in self.t.out

    def test_override_version_range_outside(self):
        # Override upstream version range with a different (non intersecting) version range
        self.t.save({"conanfile.py": GenConanfile().with_requirement("libb/[>2.x]@user/channel",
                                                                     override=True)
                                                   .with_require("libc/1.0@user/channel")})
        self.t.run("graph info . --filter requires")
        self.t.assert_overrides({'libb/[<=2.0]@user/channel': ['libb/[>2.x]@user/channel']})
        assert "libb/3.0@user/channel" in self.t.out


class TestVersionRangeOverrideFail:

    def test_override(self):
        """
        pkga -> ros_perception  -> ros_core
           \\-----> pkgb  -----------/
        """
        # https://github.com/conan-io/conan/issues/8071
        t = TestClient(light=True)
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
        assert "ros_core/1.1.4@3rdparty/unstable" in t.out
        assert "ros_perception/1.1.4@3rdparty/unstable" in t.out
        assert "snapshot" not in t.out

        t.save({"conanfile.py": GenConanfile("pkga", "0.1")
               .with_require("pkgb/[~0]@common/unstable")
               .with_require("ros_perception/pr-53@3rdparty/snapshot")
               .with_requirement("ros_core/pr-53@3rdparty/snapshot", override=True)})

        t.run("create .  --build=missing --build=pkga")
        assert "ros_core/pr-53@3rdparty/snapshot" in t.out
        assert "ros_perception/pr-53@3rdparty/snapshot" in t.out

        # Override only the upstream without overriding the direct one
        t.save({"conanfile.py": GenConanfile("pkga", "0.1")
               .with_require("pkgb/[~0]@common/unstable")
               .with_require("ros_perception/[~1.1]@3rdparty/unstable")
               .with_requirement("ros_core/pr-53@3rdparty/snapshot", force=True)})

        t.run("create .  --build=missing --build=pkga")
        assert "ros_core/pr-53@3rdparty/snapshot" in t.out
        assert "ros_perception/1.1.4@3rdparty/unstable" in t.out

        # Check information got by graph info
        t.run("graph info . --format json")
        info = json.loads(t.stdout)
        expected_overrides = {
            "ros_core/[~1.1]@3rdparty/unstable": [
                "ros_core/pr-53@3rdparty/snapshot"
            ],
            "ros_core/1.1.4@3rdparty/unstable": [
                "ros_core/pr-53@3rdparty/snapshot"
            ]
        }
        assert info['graph']["overrides"] == expected_overrides
        expected_resolved_ranges = {
            "pkgb/[~0]@common/unstable": "pkgb/0.1@common/unstable",
            "ros_perception/[~1.1]@3rdparty/unstable": "ros_perception/1.1.4@3rdparty/unstable"
        }
        assert info['graph']["resolved_ranges"] == expected_resolved_ranges
