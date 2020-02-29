# coding=utf-8

import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class QuietOutputTestCase(unittest.TestCase):

    def test_inspect(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_name("name")})
        client.run("export . name/version@user/channel")
        client.run("upload name/version@user/channel --all")
        client.run("remove * -f")

        # If the recipe exists, it doesn't show extra output
        client.run("inspect name/version@user/channel --raw name")
        self.assertEqual(client.out, "name")

        # If the recipe doesn't exist, the output is shown
        client.run("inspect non-existing/version@user/channel --raw name", assert_error=True)
        self.assertIn("ERROR: Unable to find 'non-existing/version@user/channel' in remotes",
                      client.out)
