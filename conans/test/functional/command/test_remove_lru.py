import unittest

import mock

from conans.test.utils.tools import TestClient, GenConanfile


class RemoveLRUTest(unittest.TestCase):
    def test_remove_lru_only_cache(self):
        client = TestClient()
        # This shouldn't remove anything
        client.run("remove * --old=3w -r=default", assert_error=True)
        self.assertIn("Remove old packages only work in cache, not remotes", client.out)

    def test_remove_lru(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_settings("os")})
        with mock.patch("conans.util.dates.calendar.timegm", return_value=0):
            client.run("create . dep/0.1@user/testing -s os=Linux")
            client.run("create . dep/0.1@user/testing -s os=Windows")
            client.run("create . unused/0.1@user/testing -s os=Linux")
            client.save({"conanfile.py": GenConanfile().with_settings("os")
                        .with_require("dep/0.1@user/testing")})
            client.run("create . pkg/0.1@user/testing -s os=Linux")
            client.run("create . pkg/0.1@user/testing -s os=Windows")
            # This shouldn't remove anything
            client.run("remove * --old=3d -f")
            client.run("search pkg/0.1@user/testing")
            self.assertIn("os: Linux", client.out)
            self.assertIn("os: Windows", client.out)
            client.run("search dep/0.1@user/testing")
            self.assertIn("os: Linux", client.out)
            self.assertIn("os: Windows", client.out)
            client.run("search unused/0.1@user/testing")
            self.assertIn("os: Linux", client.out)

        # 2 minutes later
        with mock.patch("conans.util.dates.calendar.timegm", return_value=120):
            client.run("install pkg/0.1@user/testing -s os=Linux")
            client.run("remove * --old=1m -f")
            client.run("search pkg/0.1@user/testing")
            self.assertIn("os: Linux", client.out)
            self.assertNotIn("os: Windows", client.out)
            client.run("search dep/0.1@user/testing")
            self.assertIn("os: Linux", client.out)
            self.assertNotIn("os: Windows", client.out)
            client.run("search")
            self.assertNotIn("unused/0.1@user/testing", client.out)

            # remove everything
            client.run("remove * --old=0m -f")
            client.run("search")
            self.assertIn("There are no packages", client.out)
