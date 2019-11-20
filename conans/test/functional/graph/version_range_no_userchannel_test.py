# coding=utf-8

import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class VersionRangeNoUserChannelTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        
        class LibB(ConanFile):
            requires = "{}"
    """)

    def test_match(self):
        t = TestClient()
        t.save({"conanfile.py": GenConanfile(), })
        t.run("export . libB/1.0@")

        # Use version ranges without user/channel
        t.save({"conanfile.py": self.conanfile.format("libB/[~1.x]")})
        t.run("info . --only requires")
        self.assertIn("Version range '~1.x' required by 'conanfile.py'"
                      " resolved to 'libB/1.0' in local cache", t.out)

    def test_no_match(self):
        t = TestClient()
        t.save({"conanfile.py": GenConanfile(), })
        t.run("export . libB/1.0@user/channel")

        # Use version ranges without user/channel
        t.save({"conanfile.py": self.conanfile.format("libB/[~1.x]")})
        t.run("info . --only requires", assert_error=True)
        self.assertIn("ERROR: Version range '~1.x' from requirement 'libB/[~1.x]' required"
                      " by 'conanfile.py' could not be resolved in local cache", t.out)

    def test_no_match_with_userchannel(self):
        t = TestClient()
        t.save({"conanfile.py": GenConanfile(), })
        t.run("export . libB/1.0@")

        # Use version ranges with user/channel
        t.save({"conanfile.py": self.conanfile.format("libB/[~1.x]@user/channel")})
        t.run("info . --only requires", assert_error=True)
        self.assertIn("ERROR: Version range '~1.x' from requirement 'libB/[~1.x]@user/channel'"
                      " required by 'conanfile.py' could not be resolved in local cache", t.out)
