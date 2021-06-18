# coding=utf-8

import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class VersionRangeNoUserChannelTestCase(unittest.TestCase):

    def test_match(self):
        t = TestClient()
        t.save({"conanfile.py": GenConanfile(), })
        t.run("export . libB/1.0@")

        # Use version ranges without user/channel
        t.save({"conanfile.py": GenConanfile().with_require("libB/[~1.x]")})
        t.run("info . --only requires")
        self.assertIn("Version range '~1.x' required by 'conanfile.py'"
                      " resolved to 'libB/1.0' in local cache", t.out)

    def test_no_match(self):
        t = TestClient()
        t.save({"conanfile.py": GenConanfile()})
        t.run("export . libB/1.0@user/channel")

        # Use version ranges without user/channel
        t.save({"conanfile.py": GenConanfile().with_require("libB/[~1.x]")})
        t.run("info . --only requires", assert_error=True)
        self.assertIn("ERROR: Version range '~1.x' from requirement 'libB/[~1.x]' required"
                      " by 'conanfile.py' could not be resolved in local cache", t.out)

    def test_no_match_with_userchannel(self):
        t = TestClient()
        t.save({"conanfile.py": GenConanfile()})
        t.run("export . libB/1.0@")

        # Use version ranges with user/channel
        t.save({"conanfile.py": GenConanfile().with_require("libB/[~1.x]@user/channel")})
        t.run("info . --only requires", assert_error=True)
        self.assertIn("ERROR: Version range '~1.x' from requirement 'libB/[~1.x]@user/channel'"
                      " required by 'conanfile.py' could not be resolved in local cache", t.out)

    def test_mixed_user_channel(self):
        # https://github.com/conan-io/conan/issues/7846
        t = TestClient(default_server_user=True)
        t.save({"conanfile.py": GenConanfile()})
        t.run("create . pkg/1.0@")
        t.run("create . pkg/1.1@")
        t.run("create . pkg/2.0@")
        t.run("create . pkg/1.0@user/testing")
        t.run("create . pkg/1.1@user/testing")
        t.run("create . pkg/2.0@user/testing")
        t.run("upload * --all --confirm")
        t.run("remove * -f")

        t.run('install "pkg/[>0 <2]@"')
        self.assertIn("pkg/1.1 from 'default' - Downloaded", t.out)
        t.run('install "pkg/[>0 <2]@user/testing"')
        self.assertIn("pkg/1.1@user/testing from 'default' - Downloaded", t.out)
